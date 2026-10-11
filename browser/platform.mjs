// Browser capabilities only. The existing Python services validate each record.
let activeScanner;
const cancelLabel=()=>({en:'Cancel',ur:'منسوخ کریں',ps:'لغوه کول'}[document.documentElement.lang]||'Cancel');
function decoded(canvas){
  const context=canvas.getContext('2d',{willReadFrequently:true});
  const image=context.getImageData(0,0,canvas.width,canvas.height);
  const result=window.jsQR(image.data,image.width,image.height,{inversionAttempts:'attemptBoth'});
  return result?.data && result.data.length<=200 ? result.data : null;
}
function draw(image){
  const width=image.videoWidth||image.naturalWidth,height=image.videoHeight||image.naturalHeight;
  if(!width||!height)throw new Error('Invalid image');
  const ratio=Math.min(1,1600/Math.max(width,height));
  const canvas=document.createElement('canvas');canvas.width=Math.floor(width*ratio);canvas.height=Math.floor(height*ratio);
  canvas.getContext('2d').drawImage(image,0,0,canvas.width,canvas.height);return canvas;
}
export function scanQR(mode,labels={}){
  activeScanner?.();
  if(typeof window.jsQR!=='function')return Promise.resolve({payload:null,status:'unavailable'});
  if(mode==='image')return new Promise(resolve=>{
    const input=document.createElement('input');input.type='file';input.accept='image/*';input.hidden=true;document.body.append(input);
    let done=false;const finish=(payload,status)=>{if(done)return;done=true;input.remove();activeScanner=null;resolve({payload,status});};
    activeScanner=()=>finish(null,'cancelled');input.addEventListener('cancel',()=>finish(null,'cancelled'));
    input.onchange=async()=>{
      const file=input.files[0];if(!file){finish(null,'cancelled');return;}
      if(file.size>10*1024*1024){finish(null,'invalid');return;}
      try{
        const source=await new Promise((resolve,reject)=>{const reader=new FileReader();reader.onload=()=>resolve(reader.result);reader.onerror=reject;reader.readAsDataURL(file);});
        const image=new Image();image.src=source;await image.decode();const canvas=draw(image);const payload=decoded(canvas);canvas.width=canvas.height=0;
        finish(payload,payload?'success':'invalid');
      }catch{finish(null,'invalid');}
    };
    // Called in the original click, before any async work can lose activation.
    input.click();
  });
  if(mode!=='camera'||!navigator.mediaDevices?.getUserMedia)return Promise.resolve({payload:null,status:'unavailable'});
  return new Promise(resolve=>{
    const dialog=document.createElement('dialog');dialog.className='sr-qr-dialog';
    const prompt=document.createElement('p');prompt.textContent=labels.prompt||'';
    const video=document.createElement('video');video.className='sr-qr-video';video.playsInline=true;video.muted=true;video.autoplay=true;
    const cancel=document.createElement('button');cancel.type='button';cancel.textContent=cancelLabel();dialog.append(prompt,video,cancel);document.body.append(dialog);
    let finished=false,stream,timer,deadline;
    const finish=(payload,status)=>{
      if(finished)return;finished=true;clearTimeout(timer);clearTimeout(deadline);stream?.getTracks().forEach(track=>track.stop());video.srcObject=null;
      dialog.close();dialog.remove();activeScanner=null;document.removeEventListener('visibilitychange',hidden);resolve({payload,status});
    };
    const hidden=()=>{if(document.hidden)finish(null,'cancelled');};
    activeScanner=()=>finish(null,'cancelled');cancel.onclick=()=>finish(null,'cancelled');dialog.oncancel=event=>{event.preventDefault();finish(null,'cancelled');};
    document.addEventListener('visibilitychange',hidden);dialog.showModal();deadline=setTimeout(()=>finish(null,'cancelled'),90000);
    navigator.mediaDevices.getUserMedia({audio:false,video:{facingMode:{ideal:'environment'},width:{ideal:1280},height:{ideal:720}}}).then(async value=>{
      stream=value;if(finished){stream.getTracks().forEach(track=>track.stop());return;}
      video.srcObject=stream;await video.play();
      const examine=()=>{
        if(finished)return;
        try{if(video.readyState>=2){const canvas=draw(video);const payload=decoded(canvas);canvas.width=canvas.height=0;if(payload){finish(payload,'success');return;}}}
        catch{finish(null,'invalid');return;}
        timer=setTimeout(examine,250);
      };examine();
    }).catch(()=>finish(null,'unavailable'));
  });
}
export async function exportFile(response,fallbackName='SehatRaasta-file'){
  if(!response.ok)throw new Error('File unavailable');
  const headers=[...response.headers];if(!response.headers.has('Content-Disposition'))headers.push(['Content-Disposition','attachment; filename="'+fallbackName.replace(/["\\/\r\n]/g,'_')+'"']);
  return window.SRBrowser.deliverExport({status:response.status,headers,body:new Uint8Array(await response.arrayBuffer())});
}
window.SRBrowser.scanQR=scanQR;window.SRBrowser.exportFile=exportFile;
window.addEventListener('pagehide',()=>activeScanner?.());
const dismiss=window.srDismissOverlay;window.srDismissOverlay=()=>{if(activeScanner){activeScanner();return true;}return dismiss?.()||false;};
