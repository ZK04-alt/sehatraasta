const assert=require('node:assert/strict');const fs=require('node:fs');const crypto=require('node:crypto');
const {test,before,after}=require('node:test');const {fixture,openApp,ready,navigate}=require('./helpers.cjs');
let site;before(async()=>site=await fixture());after(async()=>site?.close());
async function stagedUpdate(page,character){
  const id=character.repeat(64),manifest=JSON.parse(fs.readFileSync(site.build+'/asset-manifest.json','utf8'));
  const replacements={
    'service-worker.mjs':fs.readFileSync(site.build+'/service-worker.mjs','utf8').replace(/const BUILD_ID='[^']+';/,"const BUILD_ID='"+id+"';"),
    'shell.mjs':fs.readFileSync(site.build+'/shell.mjs','utf8').replace(/const BUILD_ID='[^']+';/,"const BUILD_ID='"+id+"';"),
    'bridge.js':fs.readFileSync(site.build+'/bridge.js','utf8')+'\nwindow.releaseSentinel="'+id+'";\n'
  };
  manifest.asset_set=id;
  for(const[name,content]of Object.entries(replacements)){
    site.overrides.set(name,content);const item=manifest.assets.find(item=>item.path===name);item.size=Buffer.byteLength(content);item.sha256=crypto.createHash('sha256').update(content).digest('hex');
  }
  site.overrides.set('asset-manifest.json',JSON.stringify(manifest));
  await page.evaluate(async()=>{
    const registration=await navigator.serviceWorker.getRegistration();
    const done=new Promise(resolve=>registration.addEventListener('updatefound',()=>{const worker=registration.installing;worker.addEventListener('statechange',()=>{if(worker.state==='installed')resolve();});},{once:true}));
    await registration.update();await done;
  });
}

test('rejected tab cannot update a busy writer',async()=>{
  const context=await site.browser.newContext();await context.addInitScript(()=>{
    const original=Worker.prototype.postMessage;window.heldRequests=[];
    Worker.prototype.postMessage=function(data,...args){if(window.holdRequests&&data.type==='request'){heldRequests.push([this,data,args]);return;}return original.call(this,data,...args);};
    window.releaseRequests=()=>{window.holdRequests=false;for(const[worker,data,args]of heldRequests.splice(0))original.call(worker,data,...args);};
  });
  try{
    const {page}=await openApp(context,site.base);await stagedUpdate(page,'d');
    const second=await context.newPage();await second.goto(site.base);await second.waitForSelector('body[data-state=failed]',{timeout:180000});
    await page.evaluate(()=>window.holdRequests=true);await page.frames()[1].evaluate(url=>{srNavigate(url);},site.base+'app/patients');
    await page.waitForFunction(()=>heldRequests.length>0);
    assert.equal(await second.locator('#apply-update').isEnabled(),false,'A rejected tab can activate the global update');
    // Exercise the handler guard too, without bypassing the application's JS.
    await second.evaluate(()=>document.querySelector('#apply-update').onclick());
    assert.equal(await page.locator('body').getAttribute('data-state'),'ready');
    await page.evaluate(()=>releaseRequests());await page.waitForFunction(()=>document.querySelector('#app').dataset.url.endsWith('/patients'));
    assert.equal(await page.frames()[1].evaluate(()=>window.releaseSentinel||null),null,'A new bridge entered the old runtime');
    await page.locator('#apply-update').click();await page.waitForSelector('body[data-state=ready]',{timeout:180000});
    await page.waitForFunction(()=>document.querySelector('#app').contentWindow.releaseSentinel==='d'.repeat(64));
    assert.equal(await second.locator('body').getAttribute('data-state'),'failed');
  }finally{site.overrides.clear();await context.close();}
});

test('old unreferenced caches are bounded after successful update and reopen',async()=>{
  const context=await site.browser.newContext();try{
    const {page}=await openApp(context,site.base);
    // Old completed public-asset versions only; no patient snapshots are modified.
    await page.evaluate(async()=>{for(const letter of ['1','2','3','4']){const cache=await caches.open('sr-assets-'+letter.repeat(64));await cache.put('/sehatraasta/iphone/.complete',new Response('complete'));}});
    await stagedUpdate(page,'e');await page.locator('#apply-update').click();
    await page.waitForFunction(()=>document.querySelector('#app').contentWindow?.releaseSentinel==='e'.repeat(64),{},{timeout:180000});
    const deadline=Date.now()+15000;let keys;
    do {keys=await page.evaluate(async()=>(await caches.keys()).filter(key=>key.startsWith('sr-assets-')));if(keys.length<=2)break;await new Promise(resolve=>setTimeout(resolve,250));}while(Date.now()<deadline);
    assert.ok(keys.length<=2,'Unreferenced complete caches remain: '+keys.length);
    // Exercise real subsequent complete installs, not only synthetic cache names.
    for(const character of ['f','9']){
      await stagedUpdate(page,character);await page.locator('#apply-update').click();
      await page.waitForFunction(character=>document.querySelector('#app').contentWindow?.releaseSentinel===character.repeat(64),character,{timeout:180000});
      await ready(page);
      const end=Date.now()+15000;
      do {keys=await page.evaluate(async()=>(await caches.keys()).filter(key=>key.startsWith('sr-assets-')));if(keys.length<=2)break;await new Promise(resolve=>setTimeout(resolve,250));}while(Date.now()<end);
      assert.ok(keys.length<=2,'Caches accumulated after another complete update');
    }
    let frame=await navigate(page,site.base+'app/patients/new');await frame.locator('[name=name]').fill('Cache Recovery Demo');await frame.locator('[name=language]').selectOption('ENGLISH');await frame.locator('[name=intent][value=save]').click();
    await page.waitForFunction(()=>document.querySelector('#app').contentDocument?.body?.textContent.includes('Cache Recovery Demo'));
    if(process.env.BROWSER_ENGINE==='webkit')await site.network(false);else await context.setOffline(true);
    await page.reload();await ready(page);frame=await navigate(page,site.base+'app/patients');assert.match(await frame.locator('body').innerText(),/Cache Recovery Demo/);
  }finally{site.overrides.clear();await context.close();await site.network(true);}
});
