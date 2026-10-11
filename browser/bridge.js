// Record requests travel through messages, never through HTTP form/fetch fallback.
(() => {
  const mount='/sehatraasta/iphone/app', origin=new URL(document.documentElement.dataset.srUrl).origin;
  const pending=new Map();let next=0;
  let current=document.documentElement.dataset.srUrl || origin+mount+'/';
  const scoped=url=>url.origin===origin && (url.pathname===mount || url.pathname.startsWith(mount+'/'));
  const send=(type,extra={})=>new Promise((resolve,reject)=>{
    const id=++next,timeout=setTimeout(()=>{pending.delete(id);reject(new Error('Local app unavailable'));},180000);
    pending.set(id,{resolve,reject,timeout});parent.postMessage({type:'sr-'+type,id,...extra},origin);
  });
  window.addEventListener('message',event=>{
    if(event.source!==parent || event.origin!==origin || event.data?.type!=='sr-reply') return;
    const item=pending.get(event.data.id);if(!item)return;
    pending.delete(event.data.id);clearTimeout(item.timeout);
    if(event.data.error)item.reject(new Error('Local app unavailable'));else item.resolve(event.data.result);
  });
  window.srCurrentURL=()=>current;
  window.srRememberLocation=url=>{const target=new URL(url,current);if(scoped(target)){current=target.href;send('remember',{url:current}).catch(()=>{});}};
  window.srNavigate=url=>send('navigate',{url:new URL(url,current).href});
  window.srBack=()=>send('back');
  window.SRBrowser={deliverExport:response=>send('export',{response})};
  const nativeFetch=window.fetch.bind(window);
  window.fetch=async(input,init={})=>{
    const url=new URL(input instanceof Request?input.url:input,current);
    if(!scoped(url)) throw new Error('Request outside the local app');
    const request=new Request(url,input instanceof Request?input:init);
    if(url.pathname.startsWith(mount+'/static/')){
      if(request.method!=='GET') throw new Error('Invalid asset request');
      return nativeFetch(request);
    }
    const body=new Uint8Array(await request.arrayBuffer());
    const response=await send('fetch',{request:{method:request.method,path:url.pathname,query:url.search.slice(1),headers:[...request.headers],body}});
    return new Response(response.body,{status:response.status,headers:response.headers});
  };
  async function submit(form,submitter=null){
    const url=new URL(form.getAttribute('action')||current,current),method=(form.method||'GET').toUpperCase();
    if(!scoped(url))throw new Error('Form outside the local app');
    const values=new FormData(form);if(submitter?.name)values.set(submitter.name,submitter.value);
    let headers=[],body=new Uint8Array();
    if(method==='GET'){url.search=new URLSearchParams(values).toString();}
    else {
      const encoded=form.enctype==='multipart/form-data'?new Response(values):new Response(new URLSearchParams(values));
      headers=[['Content-Type',encoded.headers.get('Content-Type')]];body=new Uint8Array(await encoded.arrayBuffer());
    }
    return send('submit',{request:{method,path:url.pathname,query:url.search.slice(1),headers,body},url:url.href});
  }
  HTMLFormElement.prototype.submit=function(){submit(this).catch(()=>{});};
  document.addEventListener('DOMContentLoaded',()=>{
  document.addEventListener('submit',event=>{if(event.defaultPrevented)return;event.preventDefault();submit(event.target,event.submitter).catch(()=>{});});
  document.addEventListener('click',event=>{
    const link=event.target.closest('a[href]');if(!link||event.defaultPrevented||event.button!==0)return;
    const url=new URL(link.href,current);
    if(url.hash && (url.pathname===new URL(current).pathname || link.getAttribute('href').startsWith('#')))return;
    event.preventDefault();window.srNavigate(url.href).catch(()=>{});
  });
  });
  window.addEventListener('pagehide',()=>{for(const item of pending.values()){clearTimeout(item.timeout);item.reject(new Error('Page closed'));}pending.clear();});
})();
