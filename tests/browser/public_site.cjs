// Local landing preview or public Pages assembly check. Uses fictional data only.
const assert=require('node:assert/strict');const fs=require('node:fs');const path=require('node:path');const http=require('node:http');
const {execFileSync}=require('node:child_process');const {chromium}=require('playwright');
const {ready,navigate}=require('./helpers.cjs');
const preview=process.argv.includes('--preview'),build=path.resolve(process.env.IPHONE_BUILD);
const prefix='/sehatraasta/',types={'.html':'text/html','.mjs':'text/javascript','.js':'text/javascript','.css':'text/css','.svg':'image/svg+xml','.png':'image/png','.json':'application/json','.webmanifest':'application/manifest+json','.wasm':'application/wasm'};
let server,browser;
(async()=>{
  let base='https://zk04-alt.github.io/sehatraasta/';
  if(preview){
    const code="import importlib.util,json,subprocess; s=importlib.util.spec_from_file_location('pub','scripts/publish_iphone.py'); m=importlib.util.module_from_spec(s); s.loader.exec_module(m); g=lambda n:subprocess.check_output(['git','show','origin/website:'+n]).decode(); a,b=m.landing_pages(g('index.html'),g('privacy.html')); print(json.dumps({'index.html':a.decode(),'privacy.html':b.decode(),'logo.svg':g('logo.svg'),'style.css':g('style.css')}))";
    const pages=JSON.parse(execFileSync('.venv/Scripts/python.exe',['-c',code],{encoding:'utf8',env:{...process.env,PYTHONUTF8:'1'}}));
    server=http.createServer((req,res)=>{
      const url=new URL(req.url,'http://localhost'),requested=url.pathname.slice(prefix.length)||'index.html',name=requested.endsWith('/')?requested+'index.html':requested;let data;
      if(!url.pathname.startsWith(prefix)){res.writeHead(404);return res.end();}
      if(pages[name]!==undefined)data=pages[name];
      else if(name.startsWith('iphone/')){const file=path.resolve(build,name.slice(7)||'index.html');if(file.startsWith(build+path.sep)&&fs.existsSync(file)&&fs.statSync(file).isFile())data=fs.readFileSync(file);}
      if(data===undefined){res.writeHead(404);return res.end();}
      res.writeHead(200,{'Content-Type':types[path.extname(name)]||'application/octet-stream'});res.end(data);
    });
    await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));base='http://127.0.0.1:'+server.address().port+prefix;
  }
  browser=await chromium.launch({channel:'msedge',headless:true});
  const guideContext=await browser.newContext({viewport:{width:390,height:844},userAgent:'Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 Version/17.0 Mobile/15E148 Safari/604.1'});
  const guide=await guideContext.newPage();await guide.goto(base);
  assert.equal(await guide.locator('a.download').first().getAttribute('href'),'https://github.com/ZK04-alt/sehatraasta/releases/download/v1.6.0/SehatRaasta-1.6.0.apk');
  assert.equal(await guide.locator('a[href="https://github.com/ZK04-alt/sehatraasta/tree/main"]').count(),1);
  assert.ok(!(await guide.locator('.status').innerText()).includes('by Zunair Ali Khan'));
  assert.match(await guide.locator('header').innerText(),/By Zunair Ali Khan/);
  assert.ok(await guide.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),'Landing page overflows phone width');
  await guide.screenshot({path:'tmp/iphone-'+(preview?'preview':'public')+'-landing.png',fullPage:true});
  await guide.locator('a[href="iphone/"]').click();await guide.waitForSelector('body[data-state=install]');assert.equal(await guide.locator('#app').isVisible(),false);
  await guide.goto(base+'privacy.html');assert.match(await guide.locator('body').innerText(),/browser storage/);await guideContext.close();
  if(!preview){
    const manifest=await(await fetch(base+'iphone/asset-manifest.json')).json();const expected=JSON.parse(fs.readFileSync(path.join(build,'asset-manifest.json'),'utf8'));
    assert.equal(manifest.asset_set,expected.asset_set);assert.equal(manifest.source_revision,expected.source_revision);
    const context=await browser.newContext({viewport:{width:390,height:844}}),requests=[];context.on('request',request=>requests.push({url:request.url(),method:request.method()}));
    const page=await context.newPage();await page.goto(base+'iphone/');await ready(page);
    let frame=await navigate(page,base+'iphone/app/patients/new');await frame.locator('[name=name]').fill('Public Offline Demo');await frame.locator('[name=language]').selectOption('URDU');await frame.locator('[name=intent][value=save]').click();
    await page.waitForFunction(()=>document.querySelector('#app').contentDocument?.body?.textContent.includes('Public Offline Demo'));
    await context.setOffline(true);await page.reload();await ready(page);frame=await navigate(page,base+'iphone/app/patients');assert.match(await frame.locator('body').innerText(),/Public Offline Demo/);
    assert.ok(requests.every(request=>{const url=new URL(request.url),mount=prefix+'iphone/app';return request.method==='GET'&&(!url.pathname.startsWith(mount+'/')||url.pathname.startsWith(mount+'/static/'));}),'Public medical request reached HTTP');
    await context.close();console.log('Public package boot, local save, offline cold reopen and no medical HTTP PASS');
  }
  console.log((preview?'Local preview':'Public Pages')+' landing, preserved Android/source links, byline and iPhone installation guide PASS');
})().catch(error=>{console.error(error);process.exitCode=1;}).finally(async()=>{await browser?.close();if(server?.listening)await new Promise(resolve=>server.close(resolve));});
