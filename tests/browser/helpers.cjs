const fs=require('node:fs');
const path=require('node:path');
const http=require('node:http');
const {chromium,webkit}=require('playwright');
const prefix='/sehatraasta/iphone/';
const types={'.html':'text/html','.js':'text/javascript','.mjs':'text/javascript','.css':'text/css','.json':'application/json','.webmanifest':'application/manifest+json','.wasm':'application/wasm','.zip':'application/zip','.svg':'image/svg+xml','.png':'image/png','.ttf':'font/ttf','.bcmap':'application/octet-stream'};
async function fixture(directory=process.env.IPHONE_BUILD) {
  const build=path.resolve(directory),requests=[], overrides=new Map();
  const server=http.createServer((req,res)=>{
    const url=new URL(req.url,'http://localhost');requests.push({method:req.method,path:url.pathname});
    if(!url.pathname.startsWith(prefix)){res.writeHead(404);return res.end('Not found');}
    const name=decodeURIComponent(url.pathname.slice(prefix.length))||'index.html';
    if(overrides.has(name)) {
      const value=overrides.get(name);res.writeHead(value===null?404:200,{'Content-Type':types[path.extname(name)]||'application/octet-stream'});return res.end(value||'Not found');
    }
    const file=path.resolve(build,name);
    if(!file.startsWith(build+path.sep)||!fs.existsSync(file)||!fs.statSync(file).isFile()){res.writeHead(404);return res.end('Not found');}
    res.writeHead(200,{'Content-Type':types[path.extname(file)]||'application/octet-stream','Cache-Control':'no-store'});fs.createReadStream(file).pipe(res);
  });
  await new Promise(resolve=>server.listen(0,'127.0.0.1',resolve));
  const base='http://127.0.0.1:'+server.address().port+prefix;
  const engine=process.env.BROWSER_ENGINE==='webkit'?webkit:chromium;
  const browser=await engine.launch(engine===chromium?{channel:'msedge',headless:true}:{headless:true});
  const port=server.address().port;
  async function network(enabled){
    if(enabled&&!server.listening)await new Promise(resolve=>server.listen(port,'127.0.0.1',resolve));
    if(!enabled&&server.listening){server.closeAllConnections();await new Promise(resolve=>server.close(resolve));}
  }
  return {build,requests,overrides,base,browser,network,close:async()=>{await browser.close();if(server.listening)await new Promise(resolve=>server.close(resolve));}};
}
async function ready(page) {await page.waitForSelector('body[data-state=ready]',{timeout:180000});return page.frames().find(frame=>frame!==page.mainFrame());}
async function openApp(context,base) {const page=await context.newPage();await page.goto(base);const frame=await ready(page);return{page,frame};}
async function navigate(page,url) {await page.frames()[1].evaluate(url=>{window.srNavigate(url);},url);await page.waitForFunction(url=>document.querySelector('#app').dataset.url===url,url);return page.frames()[1];}
module.exports={fixture,ready,openApp,navigate,prefix};
