const assert=require('node:assert/strict');
const fs=require('node:fs');
const path=require('node:path');
const {test,before,after}=require('node:test');
const {fixture,ready,openApp,navigate}=require('./helpers.cjs');
let site;
before(async()=>{site=await fixture();});after(async()=>{if(site)await site.close();});
test('test_install_before_entry',async()=>{
  assert.ok(fs.existsSync(path.join(site.build,'index.html')),'The installable shell is missing');
  const context=await site.browser.newContext({userAgent:'Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 Version/17.0 Mobile/15E148 Safari/604.1',viewport:{width:390,height:844}});
  const page=await context.newPage();await page.goto(site.base);
  await page.waitForSelector('body[data-state=install]');
  assert.match(await page.locator('#message').innerText(),/Home Screen/);
  assert.equal(await page.locator('#app').isVisible(),false);
  const manifest=await (await page.request.get(site.base+'manifest.webmanifest')).json();
  assert.equal(manifest.display,'standalone');assert.equal(manifest.scope,'/sehatraasta/iphone/');
  assert.equal(manifest.icons.length,2);await context.close();
});
test('test_first_setup_retry',async()=>{
  site.overrides.set('app/static/fonts/PublicSans.ttf',null);
  const context=await site.browser.newContext();const page=await context.newPage();await page.goto(site.base);
  await page.waitForSelector('body[data-state=failed]',{timeout:180000});
  assert.equal(await page.locator('#app').isVisible(),false);
  site.overrides.delete('app/static/fonts/PublicSans.ttf');await page.locator('#retry').click();await ready(page);
  await context.close();
});
test('test_offline_ready_complete',async()=>{
  const context=await site.browser.newContext();const {page}=await openApp(context,site.base);
  const cached=await page.evaluate(async()=>{
    const name=(await caches.keys()).find(name=>name.startsWith('sr-assets-'));
    const cache=await caches.open(name);const urls=(await cache.keys()).map(r=>new URL(r.url).pathname);
    return{urls,complete:!!await cache.match('/sehatraasta/iphone/.complete')};
  });
  const manifest=JSON.parse(fs.readFileSync(path.join(site.build,'asset-manifest.json'),'utf8'));
  assert.ok(cached.complete);for(const asset of manifest.assets) assert.ok(cached.urls.includes('/sehatraasta/iphone/'+asset.path),asset.path);
  assert.ok(cached.urls.every(url=>!url.includes('/patients')&&!url.includes('/bundles')));
  await context.close();
});
test('test_local_route_no_network and test_shell_restarts_worker',async()=>{
  const context=await site.browser.newContext();let {page,frame}=await openApp(context,site.base);
  const start=site.requests.length;
  frame=await navigate(page,site.base+'app/patients/new');
  await frame.locator('[name=name]').fill('Offline Patient Demo');
  await frame.locator('[name=language]').selectOption('ENGLISH');
  await frame.locator('button[name=intent][value=save]').click();
  await page.waitForFunction(()=>document.querySelector('#app').contentDocument?.body?.textContent.includes('Offline Patient Demo'));
  assert.ok(site.requests.slice(start).every(r=>r.method==='GET'&&!/\/app\/(patients|bundles)/.test(r.path)),'Medical operations reached HTTP');
  if(process.env.BROWSER_ENGINE==='webkit')await site.network(false);else await context.setOffline(true);
  await page.reload();await ready(page);
  frame=await navigate(page,site.base+'app/patients');assert.match(await frame.locator('body').innerText(),/Offline Patient Demo/);
  const rejected=await frame.evaluate(async()=>{try{await fetch('/outside',{method:'POST',body:'private fixture'});return false;}catch{return true;}});
  assert.equal(rejected,true);assert.ok(!site.requests.some(r=>r.path==='/outside'));
  await context.close();await site.network(true);
});
test('test_update_keeps_dataset',async()=>{
  const context=await site.browser.newContext();let{page,frame}=await openApp(context,site.base);
  frame=await navigate(page,site.base+'app/patients/new');await frame.locator('[name=name]').fill('Update Patient Demo');await frame.locator('[name=language]').selectOption('ENGLISH');await frame.locator('button[name=intent][value=save]').click();
  await page.waitForFunction(()=>document.querySelector('#app').contentDocument?.body?.textContent.includes('Update Patient Demo'));
  const old=await page.evaluate(()=>caches.keys());
  const script=fs.readFileSync(path.join(site.build,'service-worker.mjs'),'utf8').replace(/const BUILD_ID='[^']+';/,"const BUILD_ID='"+'b'.repeat(64)+"';")+'\n// next test version\n';
  site.overrides.set('service-worker.mjs',script);
  const updated=JSON.parse(fs.readFileSync(path.join(site.build,'asset-manifest.json'),'utf8'));updated.version+='-update';updated.asset_set='b'.repeat(64);
  const asset=updated.assets.find(asset=>asset.path==='service-worker.mjs');asset.size=Buffer.byteLength(script);asset.sha256=require('node:crypto').createHash('sha256').update(script).digest('hex');
  site.overrides.set('asset-manifest.json',JSON.stringify(updated));
  site.overrides.set('runtime/pyodide.asm.wasm',null);
  await page.evaluate(async()=>{
    const reg=await navigator.serviceWorker.getRegistration();
    const result=new Promise(resolve=>reg.addEventListener('updatefound',()=>{
      const worker=reg.installing;worker.addEventListener('statechange',()=>{if(worker.state==='redundant')resolve();});
    },{once:true}));await reg.update();await result;
  });
  assert.deepEqual(await page.evaluate(()=>caches.keys()),old);
  site.overrides.clear();if(process.env.BROWSER_ENGINE==='webkit')await site.network(false);else await context.setOffline(true);await page.reload();await ready(page);
  frame=await navigate(page,site.base+'app/patients');assert.match(await frame.locator('body').innerText(),/Update Patient Demo/);await context.close();await site.network(true);
});
test('unavailable private storage stops record entry',async()=>{
  const context=await site.browser.newContext();await context.addInitScript(()=>{
    // A real storage-open failure, rather than a falsely durable in-memory store.
    IDBFactory.prototype.open=function(){throw new DOMException('Unavailable','SecurityError');};
  });
  const page=await context.newPage();await page.goto(site.base);await page.waitForSelector('body[data-state=failed]',{timeout:180000});
  assert.equal(await page.locator('#app').isVisible(),false);await context.close();
});
test('a waiting update cannot mix new assets into the active version',{skip:process.env.BROWSER_ENGINE==='webkit'},async()=>{
  const context=await site.browser.newContext();const{page}=await openApp(context,site.base);
  const script=fs.readFileSync(path.join(site.build,'service-worker.mjs'),'utf8').replace(/const BUILD_ID='[^']+';/,"const BUILD_ID='"+'a'.repeat(64)+"';")+'\n// next complete version\n';
  const shell=fs.readFileSync(path.join(site.build,'shell.mjs'),'utf8')+'\n// next asset sentinel\n';
  const manifest=JSON.parse(fs.readFileSync(path.join(site.build,'asset-manifest.json'),'utf8'));manifest.version+='-next';manifest.asset_set='a'.repeat(64);
  for(const[name,content]of[['service-worker.mjs',script],['shell.mjs',shell]]){site.overrides.set(name,content);const asset=manifest.assets.find(item=>item.path===name);asset.size=Buffer.byteLength(content);asset.sha256=require('node:crypto').createHash('sha256').update(content).digest('hex');}
  site.overrides.set('asset-manifest.json',JSON.stringify(manifest));
  await page.evaluate(async()=>{
    const reg=await navigator.serviceWorker.getRegistration();const done=new Promise(resolve=>reg.addEventListener('updatefound',()=>{const worker=reg.installing;worker.addEventListener('statechange',()=>{if(worker.state==='installed')resolve();});},{once:true}));await reg.update();await done;
  });
  const debug=await context.newCDPSession(page);await debug.send('ServiceWorker.enable');await debug.send('ServiceWorker.stopAllWorkers');
  const source=await page.evaluate(async()=>await(await fetch('./shell.mjs',{cache:'no-store'})).text());
  assert.ok(!source.includes('next asset sentinel'),'An unaccepted update replaced active assets');
  site.overrides.clear();await context.close();
});
