// Real WebAssembly acceptance gate with an isolated fictional dataset.
const assert = require('node:assert/strict');
const fs = require('node:fs');
const http = require('node:http');
const path = require('node:path');
const {chromium} = require('playwright');
const build = path.resolve(process.argv[2]);
const mount = '/sehatraasta/iphone/app';
const server = http.createServer((req, res) => {
  if(req.url === '/') {
    res.writeHead(200, {'Content-Type':'text/html'});
    return res.end('<!doctype html><title>Isolated runtime gate</title>');
  }
  const name = decodeURIComponent(new URL(req.url, 'http://localhost').pathname).replace(/^\/sehatraasta\/iphone\//, '');
  const file = path.resolve(build, name);
  if(!file.startsWith(build + path.sep) || !fs.existsSync(file) || !fs.statSync(file).isFile()) {
    res.writeHead(404); return res.end('Not found');
  }
  const mime = {'.mjs':'text/javascript','.wasm':'application/wasm','.zip':'application/zip','.json':'application/json'}[path.extname(file)] || 'application/octet-stream';
  res.writeHead(200, {'Content-Type':mime}); fs.createReadStream(file).pipe(res);
});

(async () => {
  await new Promise(resolve => server.listen(0, '127.0.0.1', resolve));
  const browser = await chromium.launch({channel:'msedge', headless:true});
  try {
    const page = await browser.newPage();
    const errors = [], requests = [];
    page.on('pageerror', error => errors.push(error.message));
    page.on('request', request => requests.push({url:request.url(),method:request.method()}));
    await page.goto('http://127.0.0.1:' + server.address().port);
    const result = await page.evaluate(async ({mount}) => {
      const worker = new Worker('/sehatraasta/iphone/runtime-worker.mjs', {type:'module'});
      const capability = crypto.randomUUID(), waiting = new Map();
      let next = 0;
      worker.onmessage = ({data}) => {
        const item = waiting.get(data.id);
        if(!item) return;
        clearTimeout(item.timeout); waiting.delete(data.id); item.resolve(data);
      };
      worker.onerror = error => {
        for(const item of waiting.values()) {clearTimeout(item.timeout);item.reject(new Error(error.message));}
        waiting.clear();
      };
      const send = (type, extra={}) => new Promise((resolve,reject) => {
        const id = ++next;
        const timeout = setTimeout(()=>reject(new Error('Worker timed out: '+type)),60000);
        waiting.set(id,{resolve,reject,timeout}); worker.postMessage({type,id,capability,...extra});
      });
      const boot = await send('bootstrap',{origin:location.origin,mount});
      if(boot.type!=='ready') throw new Error('Bootstrap failed: '+JSON.stringify(boot));
      async function request(path, method='GET', values=null) {
        let headers = [], body = new Uint8Array();
        if(values instanceof FormData) {
          const encoded = new Response(values);
          headers = [['Content-Type',encoded.headers.get('Content-Type')],['Origin',location.origin]];
          body = new Uint8Array(await encoded.arrayBuffer());
        } else if(values) {
          headers = [['Content-Type','application/x-www-form-urlencoded'],['Origin',location.origin]];
          body = new TextEncoder().encode(new URLSearchParams(values).toString());
        }
        const response = await send('request',{request:{method,path:mount+path,query:'',headers,body}});
        if(response.type!=='response') throw new Error('Request failed: '+JSON.stringify(response));
        return {text:new TextDecoder().decode(response.response.body),...response.response};
      }
      const status = (response,expected,label) => {
        if(response.status!==expected) throw new Error(label+': HTTP '+response.status+'\n'+response.text);
      };
      const token = async path => {
        const page = await request(path); status(page,200,'form');
        return /name="csrf" value="([^"]+)"/.exec(page.text)[1];
      };
      const post = async (path,values) => request(path,'POST',{csrf:await token(path),...values});
      status(await request('/'),200,'empty queue');
      status(await post('/patients/new',{name:'Amina Browser Demo',birth_year:'1980',language:'ENGLISH'}),303,'patient');
      const patients = await request('/patients');
      const patient = /\/patients\/(PT-[^"?\/]+)\?/.exec(patients.text)[1];
      const visit = await post('/bundles/new',{mode:'existing',patient_id:patient,
        creation_time:'2026-10-11T09:00',source_facility:'Demo Clinic',destination:'Demo Hospital',status:'DRAFT'});
      status(visit,303,'visit');
      const visitLocation = visit.headers.find(([key])=>key.toLowerCase()==='location')[1];
      const visitPath = visitLocation.slice(mount.length).split('?')[0];
      for(const amount of ['2500.10','0.20']) status(await post(visitPath+'/costs/new',{
        category:'TRAVEL',amount,date:'2026-10-11',source:'demo interview response',
        source_type:'reported',source_identifier:'DEMO-INTERVIEW'}),303,'cost');
      const costs = await request(visitPath+'/costs');
      if(!costs.text.includes('2500.30')&&!costs.text.includes('2,500.30')) throw new Error('Exact cost total is missing');
      const form = new FormData(); form.set('csrf',await token(visitPath+'/attachments/new'));
      for(const [key,value] of Object.entries({category:'OTHER',date:'2026-10-11',source_type:'NOT_SUPPLIED',synthetic:'yes'})) form.set(key,value);
      form.set('file',new File(['%PDF-1.4\nFictional runtime original\n%%EOF'],'Demo.pdf',{type:'application/pdf'}));
      status(await request(visitPath+'/attachments/new','POST',form),303,'document upload');
      const backup = await post('/backups',{confirm:'yes'}); status(backup,200,'backup');
      if(backup.body[0]!==80||backup.body[1]!==75) throw new Error('Backup is not a ZIP archive');
      status(await request(visitPath+'/print'),200,'report');
      worker.terminate();
      return {patient,visit:visitPath,backupBytes:backup.body.length,exactTotal:'2500.30',queue:true,upload:true,report:true};
    },{mount});
    assert.deepEqual(errors,[]);
    assert.ok(requests.every(request=>request.method==='GET'),'Record operations reached HTTP');
    assert.ok(requests.every(request=>new URL(request.url).hostname==='127.0.0.1'),'Third-party request');
    console.log('Runtime gate PASS',JSON.stringify(result));
  } finally {await browser.close();server.close();}
})().catch(error=>{console.error(error);server.close();process.exitCode=1;});
