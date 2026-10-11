const base='/sehatraasta/iphone/',mount=base+'app',marker=base+'.complete';
const BUILD_ID='__BUILD_ID__';
const owners=new Map();
const hexadecimal=buffer=>[...new Uint8Array(buffer)].map(v=>v.toString(16).padStart(2,'0')).join('');
const digest=async bytes=>hexadecimal(await crypto.subtle.digest('SHA-256',bytes));
const safe=path=>typeof path==='string' && path && !path.startsWith('/') && !/[\\\x00]/.test(path) && !path.split('/').some(p=>p==='..'||p==='.'||!p);
async function completedCache(){
  const cache=await caches.open('sr-assets-'+BUILD_ID);
  return await cache.match(marker)?cache:null;
}
self.addEventListener('install',event=>event.waitUntil((async()=>{
  const result=await fetch(base+'asset-manifest.json',{cache:'no-store'});if(!result.ok)throw new Error('Incomplete setup');
  const bytes=await result.arrayBuffer(),manifest=JSON.parse(new TextDecoder().decode(bytes));
  if(manifest.asset_set!==BUILD_ID||!Array.isArray(manifest.assets)||manifest.assets.length<10)throw new Error('Invalid package');
  const name='sr-assets-'+BUILD_ID,cache=await caches.open(name);
  if(await cache.match(marker))return;
  try {
    const names=new Set();for(const item of manifest.assets){if(!safe(item.path)||names.has(item.path)||!/^\w{64}$/.test(item.sha256))throw new Error('Invalid asset');names.add(item.path);}
    let next=0;
    await Promise.all(Array.from({length:6},async()=>{
      while(next<manifest.assets.length){const item=manifest.assets[next++];
        const response=await fetch(base+item.path,{cache:'no-store'});if(!response.ok)throw new Error('Incomplete asset');
        const content=await response.arrayBuffer();if(content.byteLength!==item.size || await digest(content)!==item.sha256)throw new Error('Changed asset');
        await cache.put(base+item.path,new Response(content,{headers:response.headers}));
      }
    }));
    await cache.put(base+'asset-manifest.json',new Response(bytes,{headers:{'Content-Type':'application/json'}}));
    await cache.put(marker,new Response('complete'));
  }catch(error){await caches.delete(name);throw error;}
})()));
self.addEventListener('activate',event=>event.waitUntil(self.clients.claim()));
self.addEventListener('message',event=>{
  const url=event.source?.url?new URL(event.source.url):null;
  if(!url || url.origin!==self.location.origin || ![base,base+'index.html'].includes(url.pathname))return;
  if(event.data?.type==='register-shell' && typeof event.data.token==='string' && event.data.token.length>=16){owners.set(event.source.id,event.data.token);event.ports[0]?.postMessage({ready:true});}
  if(event.data?.type==='activate-update')self.skipWaiting();
});
const unavailable=()=>new Response('Open SehatRaasta from its Home Screen icon. Your records were not sent to a server.',{status:503,headers:{'Content-Type':'text/plain','Cache-Control':'no-store'}});
async function localRequest(event){
  const clients=await self.clients.matchAll({type:'window'});const shell=clients.find(client=>owners.has(client.id));
  if(!shell)return unavailable();
  const channel=new MessageChannel();
  return new Promise(resolve=>{
    const timeout=setTimeout(()=>{channel.port1.close();resolve(unavailable());},180000);
    channel.port1.onmessage=({data})=>{clearTimeout(timeout);channel.port1.close();
      if(!data?.response)return resolve(unavailable());
      resolve(new Response(data.response.body,{status:data.response.status,headers:data.response.headers}));
    };
    const url=new URL(event.request.url);
    event.request.arrayBuffer().then(body=>shell.postMessage({type:'local-request',token:owners.get(shell.id),request:{method:event.request.method,path:url.pathname,query:url.search.slice(1),headers:[...event.request.headers],body:new Uint8Array(body)}},[channel.port2])).catch(()=>{clearTimeout(timeout);resolve(unavailable());});
  });
}
self.addEventListener('fetch',event=>{
  const url=new URL(event.request.url);
  const dynamic=(url.pathname===mount || url.pathname.startsWith(mount+'/')) && !url.pathname.startsWith(mount+'/static/');
  if(dynamic){event.respondWith(localRequest(event));return;}
  // No uncontrolled network fallback, including requests outside the app scope.
  event.respondWith((async()=>{
    if(event.request.method!=='GET'||url.origin!==self.location.origin||!url.pathname.startsWith(base))return unavailable();
    const cache=await completedCache();if(!cache)return unavailable();
    const key=url.pathname===base?base+'index.html':url.pathname;
    return await cache.match(key) || unavailable();
  })());
});
