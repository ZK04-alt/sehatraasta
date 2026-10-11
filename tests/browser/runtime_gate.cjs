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
  if(req.url === '/sehatraasta/iphone/fault-worker.mjs') {
    res.writeHead(200,{'Content-Type':'text/javascript'});
    return res.end(`let armed=false;const early=[];self.onmessage=event=>early.push(event);const put=IDBObjectStore.prototype.put;
      IDBObjectStore.prototype.put=function(value,...args){
        if(armed&&value?.bytes?.length>1048576) throw new DOMException('Injected storage failure','QuotaExceededError');
        return put.call(this,value,...args);
      };
      self.addEventListener('message',event=>{if(event.data.type==='arm-storage-fault') armed=true;});
      await import('./runtime-worker.mjs');for(const event of early) self.onmessage(event);`);
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
      let worker = new Worker('/sehatraasta/iphone/runtime-worker.mjs', {type:'module'});
      let capability = crypto.randomUUID();
      const owner = crypto.randomUUID(), waiting = new Map();
      let next = 0;
      const receive = ({data}) => {
        const item = waiting.get(data.id);
        if(!item) return;
        clearTimeout(item.timeout); waiting.delete(data.id); item.resolve(data);
      };
      const failed = error => {
        for(const item of waiting.values()) {clearTimeout(item.timeout);item.reject(new Error(error.message));}
        waiting.clear();
      };
      worker.onmessage=receive;worker.onerror=failed;
      const send = (type, extra={}) => new Promise((resolve,reject) => {
        const id = ++next;
        const timeout = setTimeout(()=>reject(new Error('Worker timed out: '+type)),60000);
        waiting.set(id,{resolve,reject,timeout}); worker.postMessage({type,id,capability,...extra});
      });
      const boot = await send('bootstrap',{origin:location.origin,mount,owner});
      if(boot.type!=='ready') throw new Error('Bootstrap failed: '+JSON.stringify(boot));
      const second=new Worker('/sehatraasta/iphone/runtime-worker.mjs',{type:'module'});
      const conflict=await new Promise(resolve=>{
        second.onmessage=({data})=>resolve(data);
        second.postMessage({type:'bootstrap',id:1,origin:location.origin,mount,owner:crypto.randomUUID(),capability:crypto.randomUUID()});
      });
      second.terminate();
      if(conflict.type!=='failure'||conflict.code!=='SnapshotConflict') throw new Error('Second worker acquired the active dataset');
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
      const multipart = async (path,values,fileName,content) => {
        const page=await request(path);status(page,200,'multipart form');
        const data=new FormData();
        for(const match of page.text.matchAll(/<input[^>]*type="hidden"[^>]*name="([^"]+)"[^>]*value="([^"]*)"/g)) data.set(match[1],match[2]);
        for(const [key,value] of Object.entries(values)) data.set(key,value);
        data.set('file',new File([content],fileName,{type:'application/pdf'}));
        return request(path,'POST',data);
      };
      const confirm = async path => {
        const page=await request(path);status(page,200,'confirmation form');
        const fields={confirm:'yes',csrf:/name="csrf" value="([^"]+)"/.exec(page.text)[1]};
        const revision=/name="revision" value="([^"]+)"/.exec(page.text);if(revision) fields.revision=revision[1];
        return request(path,'POST',fields);
      };
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
      const documents=await request(visitPath+'/attachments');
      const document=/\/attachments\/(AT-[^"?\/]+)\//.exec(documents.text)[1];
      status(await multipart(visitPath+'/attachments/new',{category:'OTHER',date:'2026-10-11',source_type:'NOT_SUPPLIED'},'Rejected.pdf','Not a PDF'),422,'rejected original');
      status(await multipart('/attachments/'+document+'/replace',{},'Replacement.pdf','%PDF-1.4\nReplacement fictional original\n%%EOF'),303,'replace');
      const replacement=await request('/attachments/'+document+'/content');
      if(!replacement.text.includes('Replacement fictional original')) throw new Error('Replacement missing');
      status(await confirm('/attachments/'+document+'/delete'),303,'remove document');
      const removed=await request('/removed');
      const removedId=/\/removed\/([^"?\/]+)\/restore/.exec(removed.text)[1];
      status(await confirm('/removed/'+removedId+'/restore'),303,'restore document');
      status(await request('/attachments/'+document+'/content'),200,'restored original');
      status(await confirm('/attachments/'+document+'/delete'),303,'remove again');
      const again=await request('/removed');
      const permanentId=/\/removed\/([^"?\/]+)\/permanent/.exec(again.text)[1];
      status(await confirm('/removed/'+permanentId+'/permanent'),303,'permanent deletion');
      status(await request('/attachments/'+document+'/content'),404,'deleted original');
      // Restore the original complete dataset, including its original file.
      status(await post('/patients/new',{name:'Later Browser Demo',language:'ENGLISH'}),303,'later patient');
      for(const intent of ['check','restore']) {
        const data=new FormData();data.set('csrf',await token('/restore'));data.set('intent',intent);
        data.set('archive',new File([backup.body],'backup.zip',{type:'application/zip'}));
        status(await request('/restore','POST',data),200,'full backup '+intent);
      }
      const restoredPatients=await request('/patients');
      if(restoredPatients.text.includes('Later Browser Demo')) throw new Error('Restore did not activate the archived dataset');
      const restoredOriginal=await request('/attachments/'+document+'/content');
      if(!restoredOriginal.text.includes('Fictional runtime original')) throw new Error('Original bytes not restored');
      status(await request(visitPath+'/print'),200,'report');
      worker.terminate();
      worker = new Worker('/sehatraasta/iphone/fault-worker.mjs',{type:'module'});
      worker.onmessage=receive;worker.onerror=failed;capability=crypto.randomUUID();
      const restart = await send('bootstrap',{origin:location.origin,mount,owner});
      if(restart.type!=='ready') throw new Error('Restart failed: '+JSON.stringify(restart));
      status(await request('/patients/'+patient),200,'patient after restart');
      const reopenedCosts=await request(visitPath+'/costs');
      if(!reopenedCosts.text.includes('2500.30')&&!reopenedCosts.text.includes('2,500.30')) throw new Error('Costs lost after restart');
      const reopenedDocuments=await request(visitPath+'/attachments');
      if(!reopenedDocuments.text.includes('Demo.pdf')) throw new Error('Original lost after restart');
      const failingData=new FormData();failingData.set('csrf',await token(visitPath+'/attachments/new'));
      for(const [key,value] of Object.entries({category:'OTHER',date:'2026-10-11',source_type:'NOT_SUPPLIED'})) failingData.set(key,value);
      failingData.set('file',new File(['%PDF-1.4\n',new Uint8Array(2*1024*1024),'\n%%EOF'],'Quota.pdf',{type:'application/pdf'}));
      const encoded=new Response(failingData);
      worker.postMessage({type:'arm-storage-fault'});
      const failedWrite=await send('request',{request:{method:'POST',path:mount+visitPath+'/attachments/new',query:'',
        headers:[['Content-Type',encoded.headers.get('Content-Type')],['Origin',location.origin]],body:new Uint8Array(await encoded.arrayBuffer())}});
      if(failedWrite.type!=='failure'||failedWrite.code!=='SnapshotWriteError') throw new Error('Durable fault result: '+JSON.stringify({type:failedWrite.type,code:failedWrite.code,status:failedWrite.response?.status}));
      const frozen=await send('request',{request:{method:'GET',path:mount+'/',query:'',headers:[],body:new Uint8Array()}});
      if(frozen.type!=='failure') throw new Error('Unconfirmed dataset remained writable');
      worker.terminate();
      worker=new Worker('/sehatraasta/iphone/runtime-worker.mjs',{type:'module'});
      worker.onmessage=receive;worker.onerror=failed;capability=crypto.randomUUID();
      if((await send('bootstrap',{origin:location.origin,mount,owner})).type!=='ready') throw new Error('Quota recovery failed');
      const lastConfirmed=await request(visitPath+'/attachments');
      if(lastConfirmed.text.includes('Quota.pdf')||!lastConfirmed.text.includes('Demo.pdf')) throw new Error('Quota failure damaged the confirmed snapshot');
      worker.terminate();
      return {patient,visit:visitPath,backupBytes:backup.body.length,exactTotal:'2500.30',queue:true,upload:true,report:true,restarted:true,rejected:true,replaced:true,removed:true,permanentlyDeleted:true,fullRestore:true,secondWorkerRejected:true,quotaRollback:true};
    },{mount});
    assert.deepEqual(errors,[]);
    assert.ok(requests.every(request=>request.method==='GET'),'Record operations reached HTTP');
    assert.ok(requests.every(request=>new URL(request.url).hostname==='127.0.0.1'),'Third-party request');
    console.log('Runtime gate PASS',JSON.stringify(result));
  } finally {await browser.close();server.close();}
})().catch(error=>{console.error(error);server.close();process.exitCode=1;});
