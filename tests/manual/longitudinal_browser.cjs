// Twenty actual fictional paper saves; this is not a participant study.
const {chromium}=require('playwright');
const assert=require('node:assert/strict');
const fs=require('node:fs');
(async()=>{
 const channel=process.env.SR_BROWSER_CHANNEL||'msedge';
 const browser=await chromium.launch({...(channel==='chromium'?{}:{channel}),headless:true});
 try {
  const page=await browser.newPage({viewport:{width:360,height:800}});
  const errors=[];page.on('pageerror',error=>errors.push(error.message));
  const visits=[];const start=Date.now();
  for(let number=1;number<=20;number++) {
   await page.goto('http://127.0.0.1:5091/documents/new?patient_id=PK-002&lang=en');
   assert.equal(await page.locator('#patient_id').inputValue(),'PK-002');
   const png=await page.evaluate(number=>{const canvas=document.createElement('canvas');canvas.width=canvas.height=1;canvas.getContext('2d').fillStyle=`rgb(${100+number},23,167)`;canvas.getContext('2d').fillRect(0,0,1,1);return canvas.toDataURL().split(',')[1];},number);
   const filename='fictional-routine-paper-'+String(number).padStart(2,'0')+'.png';
   await page.locator('#file').setInputFiles({name:filename,mimeType:'image/png',buffer:Buffer.from(png,'base64')});
   await page.locator('button[value=save]').click();await page.waitForURL('**/bundles/**');
   const text=await page.locator('main').innerText();
   assert.ok(text.includes(filename)&&text.includes('1990')&&text.includes('Date not known'));
   visits.push(new URL(page.url()).pathname);
  }
  assert.equal(new Set(visits).size,20);
  await page.goto('http://127.0.0.1:5091/?q=fictional-routine-paper-&lang=en');
  assert.equal(await page.locator('.referral-card').count(),20,'Every saved paper remains findable');
  await page.goto('http://127.0.0.1:5091/?q=fictional-routine-paper-20.png&lang=en');
  assert.equal(await page.locator('.referral-card').count(),1);
  await page.locator('.referral-card > a').click();await page.waitForURL('**'+visits[19]+'*');
  const download=await page.locator('#attachments a[href*="/download"]').first().getAttribute('href');
  const response=await page.request.get(new URL(download,page.url()).href);
  assert.equal(response.status(),200);assert.ok((await response.body()).length>0);
  assert.deepEqual(errors,[]);fs.mkdirSync('tmp/longitudinal-browser',{recursive:true});
  await page.screenshot({path:'tmp/longitudinal-browser/twentieth-paper.png',fullPage:true});
  const result={savedPapers:20,distinctVisits:20,requiredTypedMetadataPerPaper:0,fileChoicesPerPaper:1,saveActionsPerPaper:1,elapsedMs:Date.now()-start,pageErrors:errors,humanStudy:false};
  fs.writeFileSync('tmp/longitudinal-browser/results.json',JSON.stringify(result,null,2));
  console.log('PASS: twenty known-patient saves without repeated metadata; all20found; twentieth original retrieved',JSON.stringify(result));
 } finally {await browser.close();}
})().catch(error=>{console.error(error);process.exitCode=1;});
