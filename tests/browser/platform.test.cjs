const assert=require('node:assert/strict');
const fs=require('node:fs');const path=require('node:path');
const JSZip=require('jszip');
const {test,before,after}=require('node:test');
const {fixture,openApp,navigate}=require('./helpers.cjs');
let site,context,page,frame,visit,patient,qr,backup,passport;
const documents=path.resolve(process.env.REPORT_FIXTURES||'tmp/iphone-report-fixtures-20261012');
const output=path.resolve('tmp/iphone-platform-'+(process.env.BROWSER_ENGINE||'chromium'));
async function go(url){frame=await navigate(page,url.startsWith('http')?url:site.base+'app'+url);return frame;}
async function submitted(predicate){await page.waitForFunction(predicate);frame=page.frames()[1];}
async function upload(name,content,type='application/pdf'){
  await go(visit+'/attachments/new');await frame.locator('[name=file]').setInputFiles({name,mimeType:type,buffer:content});
  await frame.locator('[name=source_type]').selectOption('NOT_SUPPLIED');await frame.locator('[name=intent][value=save]').click();
  await submitted(()=>document.querySelector('#app').contentDocument?.querySelector('.status'));
}
async function exported(){
  await page.locator('#export').waitFor({state:'visible'});const downloading=page.waitForEvent('download');await page.locator('#save-file').click();
  const file=await downloading;const destination=path.join(output,file.suggestedFilename());await file.saveAs(destination);await page.locator('#close-export').click();return fs.readFileSync(destination);
}
async function report(){await go(visit+'/print');await frame.waitForFunction(()=>document.documentElement.dataset.reportReady==='yes'||document.querySelector('#report-status')?.getAttribute('role')==='alert',{},{timeout:60000});}
before(async()=>{
  fs.mkdirSync(output,{recursive:true});site=await fixture();context=await site.browser.newContext({viewport:{width:390,height:844},acceptDownloads:true});
  ({page,frame}=await openApp(context,site.base));
  await go('/documents/new');await frame.locator('[name=name]').fill('Amina Platform Demo');
  await frame.locator('[name=file]').setInputFiles({name:'Three pages.pdf',mimeType:'application/pdf',buffer:fs.readFileSync(path.join(documents,'three-pages.pdf'))});
  await frame.locator('[name=intent][value=save]').click();
  await submitted(()=>/\/bundles\/SR-/.test(document.querySelector('#app').dataset.url));
  visit=new URL(await frame.evaluate(()=>srCurrentURL())).pathname.replace('/sehatraasta/iphone/app','');
  await go('/patients');const href=await frame.locator('a[href*="/patients/PT-"]').first().getAttribute('href');patient=new URL(href,site.base).pathname.split('/').pop();
  await report();qr=Buffer.from((await frame.locator('img.qr').getAttribute('src')).split(',')[1],'base64');
});
after(async()=>{if(context)await context.close();if(site)await site.close();});
test('test_qr_saved_image',async()=>{
  await go('/lookup');assert.equal(await frame.evaluate(()=>typeof SRBrowser.scanQR),'function','Browser QR adapter is missing');
  const picking=page.waitForEvent('filechooser');await frame.locator('[data-scan-image]').click();const chooser=await picking;
  await chooser.setFiles({name:'Saved QR.png',mimeType:'image/png',buffer:qr});await frame.waitForFunction(()=>document.querySelector('[name=payload]').value.length>0);
  await frame.locator('[name=intent][value=save]').click();await submitted(()=>/\/bundles\/SR-/.test(document.querySelector('#app').dataset.url));
  assert.equal(new URL(await frame.evaluate(()=>srCurrentURL())).pathname,'/sehatraasta/iphone/app'+visit);
});
test('test_qr_invalid_image',async()=>{
  await go('/lookup');const picking=page.waitForEvent('filechooser');await frame.locator('[data-scan-image]').click();const chooser=await picking;
  await chooser.setFiles({name:'Invalid.png',mimeType:'image/png',buffer:Buffer.from('Not an image')});
  await frame.waitForFunction(()=>document.querySelector('[data-scan-status]').textContent.length>0);
  assert.equal(await frame.locator('[name=payload]').inputValue(),'');
});
test('test_camera_denied_keeps_image_choice',async()=>{
  await go('/lookup');await frame.evaluate(()=>{
    if(!navigator.mediaDevices)Object.defineProperty(navigator,'mediaDevices',{value:{},configurable:true});
    navigator.mediaDevices.getUserMedia=async()=>{throw new DOMException('Denied','NotAllowedError');};
  });
  await frame.locator('[data-scan-camera]').click();await frame.waitForFunction(()=>document.querySelector('[data-scan-status]').textContent.length>0);
  assert.equal(await frame.locator('[data-scan-image]').isEnabled(),true);assert.equal(await frame.locator('[name=payload]').inputValue(),'');
});

test('test_camera_decode_and_cancel_stop_tracks',async t=>{
  await go('/lookup');
  if(!await frame.evaluate(()=>typeof HTMLCanvasElement.prototype.captureStream==='function')){t.skip('Engine lacks canvas stream fixture; physical camera remains unverified');return;}
  await frame.evaluate(async source=>{
    const image=new Image();image.src=source;await image.decode();
    const canvas=document.createElement('canvas');canvas.width=canvas.height=400;
    canvas.getContext('2d').drawImage(image,0,0,400,400);
    window.testStream=canvas.captureStream(5);window.testCanvas=canvas;
    navigator.mediaDevices.getUserMedia=async()=>window.testStream;
  },'data:image/png;base64,'+qr.toString('base64'));
  await frame.locator('[data-scan-camera]').click();
  try {await frame.waitForFunction(()=>document.querySelector('[name=payload]').value.length>0);}
  catch(error){console.error(await frame.evaluate(()=>({status:document.querySelector('[data-scan-status]').textContent,video:document.querySelector('video')&&{ready:document.querySelector('video').readyState,width:document.querySelector('video').videoWidth,paused:document.querySelector('video').paused},tracks:testStream.getTracks().map(track=>track.readyState)})));throw error;}
  assert.ok(await frame.evaluate(()=>testStream.getTracks().every(track=>track.readyState==='ended')));
  await go('/lookup');await frame.evaluate(()=>{
    const canvas=document.createElement('canvas');canvas.width=canvas.height=300;canvas.getContext('2d').fillRect(0,0,300,300);
    window.testCanvas=canvas;window.testStream=canvas.captureStream(5);navigator.mediaDevices.getUserMedia=async()=>testStream;
  });
  await frame.locator('[data-scan-camera]').click();await frame.locator('.sr-qr-dialog button').click();
  assert.ok(await frame.evaluate(()=>testStream.getTracks().every(track=>track.readyState==='ended')));
});
test('test_full_backup_download',async()=>{
  await go('/backups');await frame.locator('[name=confirm]').check();await frame.locator('[name=intent][value=save]').click();backup=await exported();
  const archive=await JSZip.loadAsync(backup);assert.ok(archive.file('manifest.json'));assert.ok(archive.file('dataset.json'));assert.ok(Object.keys(archive.files).some(name=>name.endsWith('.pdf')));
});
test('test_passport_export_import',async()=>{
  await go(visit);const form=frame.locator('form[action*="/passport"]');await frame.locator('details').filter({has:form}).locator('summary').click();await form.locator('[name=confirm]').check();await form.locator('button').click();passport=await exported();
  const archive=await JSZip.loadAsync(passport);assert.ok(Object.keys(archive.files).some(name=>name.endsWith('.pdf')));
  const other=await site.browser.newContext({acceptDownloads:true});try{
    const opened=await openApp(other,site.base);let imported=await navigate(opened.page,site.base+'app/passports/import');
    for(const intent of ['check','import']){
      await imported.locator('[name=archive]').setInputFiles({name:'passport.zip',mimeType:'application/zip',buffer:passport});await imported.locator('[name=intent][value='+intent+']').click();
      await opened.page.waitForFunction(intent=>intent==='check'?!!document.querySelector('#app').contentDocument?.querySelector('[name=intent][value=import]'):/\/bundles\/SR-/.test(document.querySelector('#app').dataset.url),intent);
      imported=opened.page.frames()[1];
    }
    assert.match(await imported.locator('body').innerText(),/Amina Platform Demo/);
    await other.close();
  }finally{if(other)await other.close();}
});
test('test_report_all_selected_pages',async()=>{
  await upload('Embedded font.pdf',fs.readFileSync(path.join(documents,'embedded-font.pdf')));
  await upload('Synthetic image.png',fs.readFileSync(path.join(site.build,'icon-192.png')),'image/png');
  await report();assert.equal(await frame.locator('#report-print').isEnabled(),true);assert.equal(await frame.locator('.document-page').count(),6);
  assert.equal(await frame.evaluate(()=>getComputedStyle(document.body).backgroundColor),'rgb(255, 255, 255)');
  await frame.locator('body').screenshot({path:path.join(output,'doctor-report.png')});
  if(process.env.BROWSER_ENGINE!=='webkit'){
    const html=await frame.evaluate(()=>{const copy=document.documentElement.cloneNode(true);copy.querySelectorAll('script').forEach(script=>script.remove());return'<!doctype html>'+copy.outerHTML;});
    const preview=await context.newPage();await preview.goto(site.base+'index.html');await preview.waitForSelector('body[data-state=failed]',{timeout:60000});await preview.setContent(html);await preview.evaluate(()=>Promise.all([...document.images].map(image=>image.decode())));
    await preview.pdf({path:path.join(output,'doctor-report.pdf'),format:'A4',printBackground:true});await preview.close();
  }
});
test('test_report_failed_page_blocks_print',async()=>{
  await upload('Damaged.pdf',Buffer.from('%PDF-1.4\nDamaged synthetic PDF\n%%EOF'));
  await report();assert.equal(await frame.locator('#report-print').isEnabled(),false);assert.equal(await frame.locator('#report-status').getAttribute('role'),'alert');assert.match(await frame.locator('#report-status').innerText(),/Damaged.pdf/);
});

test('test_report_page_limit_blocks_print',async()=>{
  await upload('Too many.pdf',fs.readFileSync(path.join(documents,'too-many.pdf')));await report();
  const selected=await frame.locator('[data-document-name="Too many.pdf"]').getAttribute('data-url');
  const id=/attachments\/([^/]+)/.exec(selected)[1];
  await go('/patients/'+patient+'/print?preview=yes&selection=individual&visit='+visit.split('/').pop()+'&document='+id+'&lang=en');
  await frame.waitForFunction(()=>document.querySelector('#report-status')?.getAttribute('role')==='alert');
  assert.equal(await frame.locator('#report-print').isEnabled(),false);
  assert.match(await frame.locator('#report-status').innerText(),/Too many.pdf/);
});

test('test_report_missing_original_cannot_look_complete',async()=>{
  // Deliberately damage this isolated test snapshot after shutting its writer down.
  await page.evaluate(()=>window.dispatchEvent(new Event('pagehide')));
  await page.evaluate(()=>new Promise((resolve,reject)=>{
    const opening=indexedDB.open('sehatraasta-records-v1');opening.onerror=()=>reject(opening.error);
    opening.onsuccess=()=>{const db=opening.result,tx=db.transaction('files','readwrite'),store=tx.objectStore('files');
      const cursor=store.openCursor();cursor.onsuccess=()=>{const item=cursor.result;if(item){if(String(item.key).endsWith('.pdf'))item.delete();item.continue();}};
      tx.oncomplete=()=>{db.close();resolve();};tx.onabort=()=>reject(tx.error);};
  }));
  await page.reload();await page.waitForSelector('body[data-state=ready]',{timeout:180000});frame=page.frames()[1];await go(visit+'/print');
  assert.equal(await frame.locator('#report-print:enabled').count(),0);
  assert.ok(await frame.locator('body').innerText());
});
