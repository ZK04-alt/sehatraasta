import {SnapshotStore} from './storage.mjs';
const BUILD_ID='c20b74269ec394c8b4908e51cbab7a964773b17aacbba9046036cb708aaf7eb3';
const base='/sehatraasta/iphone/',mount=base+'app',origin=location.origin;
const frame=document.querySelector('#app'),message=document.querySelector('#message'),heading=document.querySelector('#heading'),retry=document.querySelector('#retry');
const words={
  en:{starting:'Opening SehatRaasta',setup:'Setting up offline use. Stay connected until this finishes.',install:'Add SehatRaasta to your Home Screen',installHelp:'In Safari, tap Share, then Add to Home Screen. Open the new icon before entering records.',failed:'SehatRaasta could not open. Nothing was sent to a server. Try again to reopen the last saved records.',conflict:'SehatRaasta is already open. Close its other window, then try again.',saveFailed:'This change was not confirmed as saved. Stop here and reopen the last saved records.',retry:'Try again',storage:'Keep regular backups in Files. Clearing website data can remove these records. Browser storage protection is not guaranteed.',ready:'Ready for offline use',save:'Save to Files',share:'Share',close:'Close',export:'Save file',update:'An update is ready. Finish this task and reopen the app to install it.'},
  ur:{starting:'سہت راستہ کھل رہا ہے',setup:'آف لائن استعمال کی تیاری جاری ہے۔ مکمل ہونے تک انٹرنیٹ سے جڑے رہیں۔',install:'سہت راستہ کو ہوم اسکرین پر شامل کریں',installHelp:'Safari میں Share، پھر Add to Home Screen دبائیں۔ معلومات درج کرنے سے پہلے نیا آئیکن کھولیں۔',failed:'ایپ نہیں کھل سکی۔ معلومات کسی سرور کو نہیں بھیجی گئیں۔ محفوظ ریکارڈ دوبارہ کھولنے کی کوشش کریں۔',conflict:'ایپ دوسری ونڈو میں کھلی ہے۔ اسے بند کرکے دوبارہ کوشش کریں۔',saveFailed:'یہ تبدیلی محفوظ ہونے کی تصدیق نہیں ہوئی۔ محفوظ ریکارڈ دوبارہ کھولیں۔',retry:'دوبارہ کوشش کریں',storage:'Files میں باقاعدہ بیک اپ رکھیں۔ ویب سائٹ کا ڈیٹا صاف کرنے سے ریکارڈ مٹ سکتے ہیں۔ براؤزر میں مستقل حفاظت کی ضمانت نہیں۔',ready:'آف لائن استعمال کے لیے تیار',save:'Files میں محفوظ کریں',share:'شیئر کریں',close:'بند کریں',export:'فائل محفوظ کریں',update:'اپ ڈیٹ تیار ہے۔ کام مکمل کرکے ایپ دوبارہ کھولیں۔'},
  ps:{starting:'سهت راسته پرانیستل کېږي',setup:'د آف لاین کارولو لپاره چمتو کېږي. تر بشپړېدو پورې له انټرنېټ سره وصل پاتې شئ.',install:'سهت راسته په Home Screen کې اضافه کړئ',installHelp:'په Safari کې Share او بیا Add to Home Screen ووهئ. د معلوماتو له لیکلو مخکې نوی نښه پرانیزئ.',failed:'اپ نه شو پرانیستل کېدای. معلومات سرور ته نه دي لېږل شوي. خوندي ریکارډونه بیا پرانیزئ.',conflict:'اپ په بله کړکۍ کې خلاص دی. هغه وتړئ او بیا هڅه وکړئ.',saveFailed:'د دې بدلون خوندي کېدل نه دي تایید شوي. خوندي ریکارډونه بیا پرانیزئ.',retry:'بیا هڅه وکړئ',storage:'په Files کې منظم بیک اپ وساتئ. د ویب پاڼې د معلوماتو پاکول ریکارډونه ړنګولای شي. د براؤزر دایمي ساتنه تضمین نه ده.',ready:'آف لاین کارولو ته چمتو',save:'په Files کې خوندي کړئ',share:'شریکول',close:'بندول',export:'فایل خوندي کړئ',update:'اپ ډیټ چمتو دی. کار بشپړ کړئ او اپ بیا پرانیزئ.'}
};
let lang='en';try{lang=localStorage.getItem('sr-language')||'en';}catch{}if(!words[lang])lang='en';
words.en.updated='This window needs to reopen after the update. Saved records are unchanged.';
words.ur.updated='اپ ڈیٹ کے بعد یہ ونڈو دوبارہ کھولیں۔ محفوظ ریکارڈ برقرار ہیں۔';
words.ps.updated='له اپ ډیټ وروسته دا کړکۍ بیا پرانیزئ. خوندي ریکارډونه پاتې دي.';
let worker,capability,registration,routeToken,seq=0,failed=false,opening=false,busy=0,updating=false,needsReload=false,current=origin+mount+'/?lang='+lang;
let controller=navigator.serviceWorker?.controller;
const waiting=new Map();let transport=Promise.resolve();
const text=key=>words[lang][key];
const canUpdate=()=>!failed&&!opening&&!updating&&!!worker&&busy===0&&document.body.dataset.state==='ready';
function state(name,key){document.body.dataset.state=name;heading.textContent=text(name==='install'?'install':'starting');message.textContent=text(key);retry.hidden=name!=='failed';retry.textContent=text('retry');document.querySelector('#storage-note').textContent=name==='install'?'':text('storage');frame.hidden=name!=='ready';document.querySelector('#apply-update').disabled=!canUpdate();if(name==='failed')document.querySelector('#update-notice').hidden=true;}
function language(code){lang=code;document.documentElement.lang=lang;document.documentElement.dir=lang==='en'?'ltr':'rtl';try{localStorage.setItem('sr-language',lang);}catch{}document.querySelectorAll('[data-lang]').forEach(b=>b.setAttribute('aria-current',String(b.dataset.lang===lang)));}
language(lang);document.querySelectorAll('[data-lang]').forEach(button=>button.onclick=()=>{language(button.dataset.lang);if(document.body.dataset.state==='install')state('install','installHelp');else start();});
const scoped=url=>url.origin===origin && (url.pathname===mount || url.pathname.startsWith(mount+'/'));
function fail(code='startup'){
  failed=true;worker?.terminate();frame.hidden=true;
  for(const item of waiting.values()){clearTimeout(item.timeout);item.reject(new Error('Local runtime stopped'));}waiting.clear();
  state('failed',code==='SnapshotConflict'?'conflict':code==='request'?'saveFailed':'failed');
}
function call(type,extra={}){return new Promise((resolve,reject)=>{
  const id=++seq,timeout=setTimeout(()=>{waiting.delete(id);fail();reject(new Error('Local runtime timed out'));},180000);
  waiting.set(id,{resolve,reject,timeout});worker.postMessage({type,id,capability,...extra});
});}
async function invoke(input){
  if(failed||!worker)throw new Error('Unavailable');
  const url=new URL(input.path+(input.query?'?'+input.query:''),origin);
  if(!scoped(url)||!['GET','HEAD','POST'].includes(input.method)||(input.body?.byteLength||0)>102*1024*1024)throw new Error('Invalid local request');
  const request={...input,headers:(input.headers||[]).filter(([key])=>!['origin','host','cookie'].includes(key.toLowerCase()))};
  if(input.method==='POST')request.headers.push(['Origin',origin]);
  busy++;document.querySelector('#apply-update').disabled=true;try{const result=await call('request',{request});return result.response;}finally{busy--;document.querySelector('#apply-update').disabled=!canUpdate();}
}
async function follow(input){let response,url=new URL(input.path+(input.query?'?'+input.query:''),origin);
  for(let count=0;count<8;count++){
    response=await invoke({...input,path:url.pathname,query:url.search.slice(1)});
    if(![301,302,303,307,308].includes(response.status))return{response,url:url.href};
    const target=response.headers.find(([key])=>key.toLowerCase()==='location');if(!target)throw new Error('Invalid local redirect');
    url=new URL(target[1],url);if(!scoped(url))throw new Error('Redirect outside local app');
    if([301,302,303].includes(response.status))input={method:'GET',headers:[],body:new Uint8Array()};
  }throw new Error('Redirect loop');
}
function render(result,replace=false){
  const contentType=result.response.headers.find(([key])=>key.toLowerCase()==='content-type')?.[1]||'';
  if(!contentType.includes('text/html')){exportFile(result.response);return;}
  current=result.url;const url=new URL(current);if(words[url.searchParams.get('lang')])language(url.searchParams.get('lang'));
  const html=new DOMParser().parseFromString(new TextDecoder().decode(result.response.body),'text/html');
  html.documentElement.dataset.srUrl=current;
  const csp=result.response.headers.find(([key])=>key.toLowerCase()==='content-security-policy')?.[1];
  if(csp){const meta=html.createElement('meta');meta.httpEquiv='Content-Security-Policy';meta.content=csp.replace(/frame-ancestors [^;]+;?/,'');html.head.prepend(meta);}
  frame.srcdoc='<!doctype html>'+html.documentElement.outerHTML;
  frame.onload=()=>{frame.dataset.url=current;state('ready','ready');};
  if(replace)history.replaceState({srUrl:current},'');else history.pushState({srUrl:current},'');
}
async function navigate(url,replace=false){const target=new URL(url,current);if(!scoped(target))throw new Error('Invalid navigation');render(await follow({method:'GET',path:target.pathname,query:target.search.slice(1),headers:[],body:new Uint8Array()}),replace);}
function exportFile(response){
  const headers=new Headers(response.headers),disposition=headers.get('content-disposition')||'';
  let name=/filename="?([^";]+)"?/.exec(disposition)?.[1]||'SehatRaasta-file';
  const encoded=/filename\*=UTF-8''([^;]+)/i.exec(disposition);if(encoded){try{name=decodeURIComponent(encoded[1]);}catch{}}
  name=name.replace(/[\\/\x00-\x1f]/g,'_');
  const file=new File([response.body],name,{type:headers.get('content-type')||'application/octet-stream'});
  const dialog=document.querySelector('#export'),save=document.querySelector('#save-file'),share=document.querySelector('#share-file');
  const blob=URL.createObjectURL(file);document.querySelector('#export-title').textContent=text('export');document.querySelector('#export-name').textContent=name;
  save.href=blob;save.download=name;save.textContent=text('save');share.hidden=!navigator.canShare?.({files:[file]});share.textContent=text('share');
  share.onclick=async()=>{try{await navigator.share({files:[file]});}catch(error){if(error.name!=='AbortError')message.textContent=text('failed');}};
  document.querySelector('#close-export').textContent=text('close');document.querySelector('#close-export').onclick=()=>dialog.close();
  dialog.onclose=()=>URL.revokeObjectURL(blob);dialog.showModal();
}
window.addEventListener('message',event=>{
  if(event.source!==frame.contentWindow||event.origin!==origin||!Number.isSafeInteger(event.data?.id))return;
  const data=event.data,source=event.source,reply=(result,error=false)=>source.postMessage({type:'sr-reply',id:data.id,result,error},origin);
  transport=transport.then(async()=>{
    try{
      if(data.type==='sr-fetch'){reply(await invoke(data.request));return;}
      if(data.type==='sr-submit'){const result=await follow(data.request);reply({ok:true});setTimeout(()=>render(result),0);return;}
      if(data.type==='sr-navigate'){const target=new URL(data.url,current);if(!scoped(target))throw new Error('Out of scope');const result=await follow({method:'GET',path:target.pathname,query:target.search.slice(1),headers:[],body:new Uint8Array()});reply({ok:true});setTimeout(()=>render(result),0);return;}
      if(data.type==='sr-remember'){const url=new URL(data.url,current);if(!scoped(url))throw new Error('Out of scope');current=url.href;history.replaceState({srUrl:current},'');reply({ok:true});return;}
      if(data.type==='sr-back'){reply({ok:true});history.back();return;}
      if(data.type==='sr-export'){exportFile(data.response);reply({ok:true});return;}
      reply(null,true);
    }catch{reply(null,true);if(!failed)fail();}
  });
});
window.addEventListener('popstate',event=>{if(event.state?.srUrl)navigate(event.state.srUrl,true).catch(()=>fail());});
async function setup(){
  if(!('serviceWorker'in navigator)||!crypto.subtle||!indexedDB)throw new Error('Storage unavailable');
  const probe=await SnapshotStore.open('sr-storage-probe');probe.database.close();
  registration=await navigator.serviceWorker.register(base+'service-worker.mjs',{scope:base,type:'module'});
  const offer=()=>{if(registration.waiting){document.querySelector('#update-notice').hidden=false;document.querySelector('#update-message').textContent=text('update');document.querySelector('#apply-update').textContent=lang==='en'?'Update':text('retry');}};
  registration.addEventListener('updatefound',()=>{registration.installing?.addEventListener('statechange',offer);});offer();
  if(!registration.active){
    const installing=registration.installing||registration.waiting;
    if(!installing)throw new Error('Setup unavailable');
    await new Promise((resolve,reject)=>{const check=()=>{if(installing.state==='activated')resolve();if(installing.state==='redundant')reject(new Error('Setup incomplete'));};installing.addEventListener('statechange',check);check();});
  }
  if(!navigator.serviceWorker.controller)await new Promise(resolve=>navigator.serviceWorker.addEventListener('controllerchange',resolve,{once:true}));
  const channel=new MessageChannel();routeToken=crypto.randomUUID();
  await new Promise((resolve,reject)=>{const timer=setTimeout(()=>reject(new Error('Setup unavailable')),10000);channel.port1.onmessage=()=>{clearTimeout(timer);channel.port1.close();resolve();};navigator.serviceWorker.controller.postMessage({type:'register-shell',token:routeToken},[channel.port2]);});
  try{await navigator.storage?.persist?.();}catch{}
}
navigator.serviceWorker?.addEventListener('message',event=>{
  if(event.data?.type==='cache-version'&&event.source?.scriptURL===origin+base+'service-worker.mjs'&&event.ports[0]){
    event.ports[0].postMessage({version:BUILD_ID,retired:needsReload});return;
  }
  if(event.source!==navigator.serviceWorker.controller||event.data?.type!=='local-request'||event.data.token!==routeToken)return;
  const port=event.ports[0];if(!port)return;
  transport=transport.then(async()=>{try{port.postMessage({response:await invoke(event.data.request)});}catch{port.postMessage({failure:true});}finally{port.close();}});
});
async function start(){
  if(opening)return;opening=true;failed=false;worker?.terminate();state('starting','setup');
  try{
    await setup();worker=new Worker(base+'runtime-worker.mjs',{type:'module'});capability=crypto.randomUUID();
    worker.onerror=()=>fail();worker.onmessage=({data})=>{
      if(data.capability!==capability)return;
      if(data.type==='failure'||data.type==='storage-lost'){fail(data.stage==='request'?'request':data.code);return;}
      const item=waiting.get(data.id);if(!item)return;waiting.delete(data.id);clearTimeout(item.timeout);item.resolve(data);
    };
    await call('bootstrap',{mount,origin,owner:crypto.randomUUID()});
    await navigate(origin+mount+'/?lang='+lang,true);
    if(registration.waiting){message.textContent=text('update');}
  }catch{if(!failed)fail();}finally{opening=false;}
}
retry.onclick=()=>needsReload?location.reload():start();
document.querySelector('#apply-update').onclick=async()=>{
  if(!canUpdate()||!registration?.waiting)return;
  updating=true;frame.inert=true;document.querySelector('#apply-update').disabled=true;
  try{
    const flush=frame.contentWindow?.srFlushUnfinished;if(flush&&!await flush())return;
    await transport;
    // A fenced durable request proves this is still the actual writer.
    const proof=await invoke({method:'GET',path:mount+'/',query:'',headers:[],body:new Uint8Array()});
    await transport;if(failed||busy||proof.status!==200)throw new Error('Update unavailable');
    worker.terminate();worker=null;frame.hidden=true;
    registration.waiting.postMessage({type:'activate-update'});
  }catch{if(!failed)fail();}
  finally{if(worker&&!failed){updating=false;frame.inert=false;}document.querySelector('#apply-update').disabled=!canUpdate();}
};
navigator.serviceWorker?.addEventListener('controllerchange',async()=>{
  const previous=controller;controller=navigator.serviceWorker.controller;
  if(!previous||!controller||previous===controller)return;
  if(updating){location.reload();return;}
  // Other windows retire their old code without competing for the new writer.
  needsReload=true;frame.inert=true;document.querySelector('#apply-update').disabled=true;
  const flush=frame.contentWindow?.srFlushUnfinished;
  if(!failed&&worker){if(flush&&!await flush()){fail();return;}await transport;}
  worker?.terminate();worker=null;failed=true;state('failed','updated');
});
window.addEventListener('pagehide',()=>worker?.terminate());
const iPhone=/iPhone|iPad|iPod/.test(navigator.userAgent)||(navigator.platform==='MacIntel'&&navigator.maxTouchPoints>1);
const installed=navigator.standalone===true||matchMedia('(display-mode: standalone)').matches;
if(iPhone&&!installed)state('install','installHelp');else start();
