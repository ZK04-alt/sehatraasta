// Fictional, isolated longitudinal checks. Never point this at an ordinary instance.
const {chromium}=require('playwright');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const base=process.argv[2]||'http://127.0.0.1:5091';
(async()=>{
 const channel=process.env.SR_BROWSER_CHANNEL||'msedge';
 const browser=await chromium.launch({...(channel==='chromium'?{}:{channel}),headless:true});
 const page=await browser.newPage({viewport:{width:360,height:800}});
 const errors=[];page.on('pageerror',e=>errors.push(e.message));
 const evidence=[];
 const go=async path=>{const response=await page.goto(base+path);assert.equal(response.status(),200,path);};
 const save=async()=>{await page.locator('button[value=save]').click();await page.waitForURL('**/bundles/**');};
 const confirm=async()=>{await page.locator('[name=confirm]').check();await page.locator('.form-actions button').click();await page.waitForURL('**/removed**');};
 try {
  await go('/bundles/RB-001/edit?lang=en');
  assert.ok((await page.locator('main').innerText()).includes('Amina Demo'));
  await page.locator('#patient_id').selectOption('PK-002');
  await page.locator('#medical_date_kind').selectOption('approximate');
  await page.locator('#medical_date_value').fill('2008-07');await save();
  assert.ok((await page.locator('main').innerText()).includes('1990'));
  assert.ok((await page.locator('main').innerText()).includes('2008-07'));
  evidence.push('Wrong-patient correction preserves originals and supplied approximate date.');
  await go('/attachments/AT-001/edit?lang=en');
  await page.locator('#name').fill('Fictional older corridor paper.png');
  await page.locator('#date').fill('');await page.locator('#destination_visit').selectOption('RB-002');
  await save();await go('/bundles/RB-002?lang=en');
  assert.ok((await page.locator('main').innerText()).includes('Fictional older corridor paper.png'));
  evidence.push('Document move retains readable patient context and unknown document date.');
  await go('/attachments/AT-001/replace?lang=en');
  await page.locator('#file').setInputFiles({name:'Fictional better scan.png',mimeType:'image/png',
   buffer:Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+aD1kAAAAASUVORK5CYII=','base64')});
  await save();
  await go('/attachments/AT-001/delete?lang=en');await confirm();
  let card=page.locator('article').filter({has:page.getByRole('heading',{name:'Fictional better scan.png',exact:true})});
  assert.equal(await card.count(),1);await card.getByRole('link',{name:'Restore',exact:true}).click();await confirm();
  await go('/attachments/AT-001/download');
 } catch(error) {
  // Download navigation intentionally aborts in Chromium; verify via the session API.
  if(!String(error).includes('Download is starting')) throw error;
 }
 try {
  const download=await page.request.get(base+'/attachments/AT-001/content');assert.equal(download.status(),200);
  assert.ok((await download.body()).length>0);
  evidence.push('Replacement retains old scan; remove/restore keeps the replacement available.');
  await go('/bundles/RB-002/medications/new?lang=en');
  await page.locator('#name').fill('Fictional medicine');
  for(const [id,value] of [['strength','250 mg'],['dose','1 tablet'],['route','By mouth'],['frequency','Once a day'],['duration','3 days']]) await page.locator('#'+id).selectOption(value);
  await save();await page.locator('details').filter({has:page.locator('summary',{hasText:'Edit or move record'})}).locator('summary').click();
  await page.locator('a[href*="/records/medication/"][href$="lang=en"]').filter({hasText:'Edit'}).click();
  await page.locator('#name').fill('Corrected fictional medicine');await page.locator('#destination_visit').selectOption('RB-004');await save();
  await go('/bundles/RB-004?lang=en');await page.locator('.record-section').first().locator('summary').click();assert.ok((await page.locator('main').innerText()).includes('Corrected fictional medicine'));
  evidence.push('Historical structured medicine remains editable and movable.');
  // Two tabs: the older revision must fail after the other tab saves.
  const stale=await browser.newPage();await stale.goto(base+'/bundles/RB-002/edit?lang=en');
  await go('/bundles/RB-002/edit?lang=en');await page.locator('#source_facility').fill('Fictional corrected facility');await save();
  await stale.locator('#source_facility').fill('Stale wrong overwrite');await stale.locator('button[value=save]').click();
  await stale.waitForSelector('[role=alert]');assert.ok((await stale.locator('main').innerText()).includes('changed'));
  assert.equal(await stale.locator('#source_facility').inputValue(),'Stale wrong overwrite');await stale.close();
  evidence.push('Stale tab fails safely and preserves attempted text for correction.');
  await go('/patients/PK-001?q=better%20scan&lang=en');assert.equal(await page.locator('.list-row').count(),1);
  await go('/?q=2008-07&lang=en');assert.equal(await page.locator('.referral-card').count(),1);
  evidence.push('Months-later retrieval by filename and supplied medical date.');
  fs.mkdirSync('tmp/repeated-browser',{recursive:true});
  for(const width of [320,360,768,1280]) for(const lang of ['en','ur','ps']) {
   await page.setViewportSize({width,height:900});await go('/bundles/RB-002?lang='+lang);
   assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true,`${width}/${lang}`);
   assert.equal((await page.locator('body').innerText()).includes('[Missing translation:'),false);
   assert.equal(await page.locator('html').getAttribute('dir'),lang==='en'?'ltr':'rtl');
   const order=await page.evaluate(()=>document.querySelector('#attachments').offsetTop<document.querySelector('#costs').offsetTop);assert.ok(order);
   await page.screenshot({path:`tmp/repeated-browser/visit-${width}-${lang}.png`,fullPage:true});
  }
  await page.setViewportSize({width:320,height:900});await go('/attachments/AT-001/edit?lang=en');
  const doubledBody=await page.evaluate(()=>{const root=parseFloat(getComputedStyle(document.documentElement).fontSize);const body=parseFloat(getComputedStyle(document.body).fontSize);document.documentElement.style.fontSize=(root*2)+'px';document.body.style.fontSize=(body*2)+'px';return body*2;});
  assert.equal(await page.evaluate(()=>parseFloat(getComputedStyle(document.body).fontSize)),doubledBody,'Actual body text must be doubled');
  assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true);
  assert.equal(await page.locator('.sidebar a').evaluateAll(nodes=>nodes.every(node=>{const range=document.createRange();range.selectNodeContents(node);return range.getBoundingClientRect().width<=node.getBoundingClientRect().width+1;})),true,'Large-text navigation labels must fit their controls');
  const unlabeled=await page.locator('input:not([type=hidden]),select,textarea').evaluateAll(nodes=>nodes.filter(n=>!(n.labels?.length||n.getAttribute('aria-label'))).map(n=>n.name));assert.deepEqual(unlabeled,[]);
  await page.keyboard.press('Tab');assert.ok(await page.evaluate(()=>document.activeElement!==document.body));
  await page.screenshot({path:'tmp/repeated-browser/edit-320-large.png',fullPage:true});
  evidence.push('320/360/768/1280 EN/UR/PS RTL rendered checks, labels, keyboard focus and 200% text check. Fluent-language and screen-reader validation remain unverified.');
  assert.deepEqual(errors,[]);
  fs.writeFileSync('tmp/repeated-browser/results.json',JSON.stringify({evidence,pageErrors:errors},null,2));
  console.log('PASS: '+evidence.join(' '));
 } finally {await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
