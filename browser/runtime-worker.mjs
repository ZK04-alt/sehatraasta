// The existing Python application, isolated from the DOM and real HTTP.
import {loadPyodide} from './runtime/pyodide.mjs';

const mount = '/sehatraasta/iphone/app';
let runtime, capability, chain = Promise.resolve();

async function bootstrap(message) {
  if(runtime || capability || message.origin !== self.location.origin || message.mount !== mount) {
    throw new Error('Invalid bootstrap');
  }
  if(typeof message.capability !== 'string' || message.capability.length < 16) throw new Error('Invalid capability');
  capability = message.capability;
  runtime = await loadPyodide({indexURL:new URL('./runtime/',import.meta.url).href,
    stdout:()=>{}, stderr:()=>{}});
  const response = await fetch(new URL('./application.zip',import.meta.url));
  if(!response.ok) throw new Error('Application package unavailable');
  runtime.unpackArchive(await response.arrayBuffer(),'zip',{extractDir:'/app'});
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
  return {type:'ready',id:message.id,capability};
}

async function request(message) {
  if(!runtime || message.capability !== capability) throw new Error('Inactive session');
  const input = runtime.toPy(message.request);
  runtime.globals.set('sr_request',input);
  input.destroy();
  const result = await runtime.runPythonAsync(`
sr_response = sr_browser.handle(
    sr_request['method'], sr_request['path'], sr_request['query'],
    sr_request['headers'], bytes(sr_request['body']))
sr_response
`);
  try {
    return {type:'response',id:message.id,capability,
            response:result.toJs({dict_converter:Object.fromEntries})};
  } finally {result.destroy();runtime.globals.delete('sr_request');}
}

self.onmessage = ({data}) => {
  if(!data || !Number.isSafeInteger(data.id)) return;
  if(data.type !== 'bootstrap' && data.capability !== capability) return;
  chain = chain.then(async () => {
    try {
      const response = data.type === 'bootstrap' ? await bootstrap(data) : await request(data);
      self.postMessage(response);
    } catch(error) {
      // No patient content, traceback, original name or filesystem path leaves
      // the runtime through an error message or the browser console.
      self.postMessage({type:'failure',id:data.id,capability,
        stage:data.type === 'bootstrap' ? 'startup' : 'request',
        code:error.constructor.name});
    }
  });
};
