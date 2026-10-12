// The existing Python application, isolated from the DOM and real HTTP.
import {loadPyodide} from './runtime/pyodide.mjs';
import {SnapshotStore, SnapshotConflict, SnapshotWriteError} from './storage.mjs';

const mount = '/sehatraasta/iphone/app';
let runtime, capability, store, owner, lease, generation, releaseLock, heartbeat;
let frozen=false, chain=Promise.resolve();

async function claimWriter(message) {
  owner=message.owner;
  if(navigator.locks) {
    await new Promise((resolve,reject) => {
      navigator.locks.request('sehatraasta-writer',{ifAvailable:true},async lock => {
        if(!lock) {reject(new SnapshotConflict());return;}
        owner='sehatraasta-exclusive-worker';
        resolve();
        await new Promise(done=>{releaseLock=done;});
      }).catch(reject);
    });
  }
  store=await SnapshotStore.open('sehatraasta-records-v1');
  const saved=await store.acquire(owner);
  lease=saved.lease;generation=saved.generation;
  return saved.files;
}

async function persistFiles() {
  const result=runtime.runPython('sr_browser.collect_files()');
  let files;
  try {files=result.toJs().map(([path,bytes])=>({path,bytes}));}
  finally {result.destroy();}
  generation=await store.commit(owner,lease,generation,files);
}

async function freeze() {
  frozen=true;
  clearInterval(heartbeat);
  if(store && lease) await store.release(owner,lease).catch(()=>{});
  if(releaseLock) releaseLock();
}

async function bootstrap(message) {
  if(runtime || capability || message.origin !== self.location.origin || message.mount !== mount) {
    throw new Error('Invalid bootstrap');
  }
  if(typeof message.capability !== 'string' || message.capability.length < 16) throw new Error('Invalid capability');
  capability = message.capability;
  const files=await claimWriter(message);
  runtime = await loadPyodide({indexURL:new URL('./runtime/',import.meta.url).href,
    stdout:()=>{}, stderr:()=>{}});
  const response = await fetch(new URL('./application.zip',import.meta.url));
  if(!response.ok) throw new Error('Application package unavailable');
  runtime.unpackArchive(await response.arrayBuffer(),'zip',{extractDir:'/app'});
  for(const file of files) {
    const path='/records/'+file.path;
    if(file.path.startsWith('/') || /[\\\x00]/.test(file.path) ||
       file.path.split('/').some(part=>!part || part==='.' || part==='..')) throw new SnapshotWriteError('invalid');
    runtime.FS.mkdirTree(path.slice(0,path.lastIndexOf('/')));
    runtime.FS.writeFile(path,file.bytes,{canOwn:true});
  }
  files.length=0;
  runtime.globals.set('sr_origin',message.origin);
  await runtime.runPythonAsync(`
import sys
from pathlib import Path
sys.path.insert(0, '/app')
from sehatraasta.browser_runtime import BrowserApplication
sr_browser = BrowserApplication(Path('/records'), origin=sr_origin)
sr_check = sr_browser.handle('GET', '/sehatraasta/iphone/app/', '', [], b'')
if sr_check['status'] != 200:
    raise RuntimeError('Application startup check failed')
`);
  await persistFiles();
  heartbeat=setInterval(()=>{
    chain=chain.then(async()=>{
      if(frozen) return;
      try {await store.renew(owner,lease);}
      catch(error) {await freeze();self.postMessage({type:'storage-lost',capability,code:error.constructor.name});}
    });
  },25000);
  return {type:'ready',id:message.id,capability};
}

async function request(message) {
  if(frozen) throw new SnapshotWriteError('reopen');
  if(!runtime || message.capability !== capability) throw new Error('Inactive session');
  const input = runtime.toPy(message.request);
  runtime.globals.set('sr_request',input);
  input.destroy();
  const result = await runtime.runPythonAsync(`
sr_browser.handle(
    sr_request['method'], sr_request['path'], sr_request['query'],
    sr_request['headers'], bytes(sr_request['body']))
`);
  let response;
  try {
    response=result.toJs({dict_converter:Object.fromEntries});
  } finally {result.destroy();runtime.globals.delete('sr_request');}
  await persistFiles();
  return {type:'response',id:message.id,capability,response};
}

self.onmessage = ({data}) => {
  if(!data || !Number.isSafeInteger(data.id)) return;
  if(capability && data.capability !== capability) return;
  if(data.type !== 'bootstrap' && !capability) return;
  chain = chain.then(async () => {
    try {
      const response = data.type === 'bootstrap' ? await bootstrap(data) : await request(data);
      self.postMessage(response);
    } catch(error) {
      await freeze();
      // No patient content, traceback, original name or filesystem path leaves
      // the runtime through an error message or the browser console.
      self.postMessage({type:'failure',id:data.id,capability,
        stage:data.type === 'bootstrap' ? 'startup' : 'request',
        code:error.constructor.name});
    }
  });
};
