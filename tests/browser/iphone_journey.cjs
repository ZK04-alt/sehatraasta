// Existing product workflows in the actual offline Python browser application.
const assert=require('node:assert/strict');const fs=require('node:fs');const path=require('node:path');
const {test,before,after}=require('node:test');const {fixture,openApp,navigate,ready}=require('./helpers.cjs');
let site;before(async()=>{site=await fixture();});after(async()=>site?.close());
const pdf=fs.readFileSync('tmp/iphone-report-fixtures-20261012/three-pages.pdf');

for(const lang of ['en','ur','ps'])test('complete offline journey '+lang,async()=>{
  await site.network(true);const context=await site.browser.newContext({viewport:{width:390,height:844},acceptDownloads:true});
  let page,frame,patient,visit;const requests=[];context.on('request',r=>requests.push({url:r.url(),method:r.method(),body:r.postData()}));
  const go=async url=>{frame=await navigate(page,site.base+'app'+url+(url.includes('?')?'&':'?')+'lang='+lang);return frame;};
  async function bodyText(){await frame.locator('details.section').evaluateAll(items=>items.forEach(item=>item.open=true));return frame.locator('body').innerText();}
  async function set(name,value){const field=frame.locator('[name="'+name+'"]');
    await field.evaluate(el=>{for(let ancestor=el.parentElement;ancestor;ancestor=ancestor.parentElement)if(ancestor.tagName==='DETAILS')ancestor.open=true;});
    const tag=await field.evaluate(el=>el.tagName);if(tag==='SELECT')await field.selectOption(value);else await field.fill(value);
  }
  async function submit(selector='[name=intent][value=save]'){
    const marker=String(Date.now())+Math.random();await page.evaluate(marker=>document.querySelector('#app').addEventListener('load',()=>window.testFormComplete=marker,{once:true}),marker);
    await frame.locator(selector).click();await page.waitForFunction(marker=>window.testFormComplete===marker,marker);
    frame=page.frames()[1];
  }
  async function record(kind,values){await go(visit+'/'+kind+'/new');for(const [name,value]of Object.entries(values))await set(name,value);await submit();assert.equal(await frame.locator('#errors').count(),0,await frame.locator('body').innerText());}
  async function paper(facility,day,name='History.pdf'){
    await go('/documents/new');await set('mode','existing');await set('patient_id',patient);await set('source_facility',facility);
    await set('medical_date_kind','exact');await set('medical_date_value',day);
    await frame.locator('[name=file]').setInputFiles({name,mimeType:'application/pdf',buffer:Buffer.concat([pdf,Buffer.from('\n% '+name+'\n')])});await submit();
    assert.equal(await frame.locator('#errors').count(),0,await frame.locator('body').innerText());
    return new URL(await frame.evaluate(()=>srCurrentURL())).pathname.replace('/sehatraasta/iphone/app','');
  }
  try{
    ({page,frame}=await openApp(context,site.base));
    if(process.env.BROWSER_ENGINE==='webkit')await site.network(false);else await context.setOffline(true);
    await go('/patients/new');await set('name','Amina Journey '+lang);await set('birth_year','1980');await set('language','URDU');await submit();
    patient=(await frame.locator('a[href*="/patients/PT-"]').first().getAttribute('href')).split('/').pop().split('?')[0];
    visit=await paper('Later Demo Clinic','2026-09-12');
    await record('medications',{name:'Historical Demo medicine',strength:'__custom__',strength__custom:'12 mg',dose:'1 tablet',frequency:'Once a day',duration:'5 days'});
    await record('orders',{name:'Demo blood test',date:'2026-09-12',workflow_status:'ORDERED'});
    await record('results',{name:'Demo blood result',date:'2026-09-13',order_name:'Demo blood test',interpretation:'Fictional result only'});
    await record('imaging',{modality:'X-ray',body_part:'Knee',date:'2026-09-12',facility:'Demo radiology'});
    await record('instructions',{category:'Clinic note',language:'URDU',text:'Fictional instructions',date:'2026-09-12'});
    await go(visit+'/context');await set('medical_history','Fictional prior history');await set('department','Orthopaedics');await submit();assert.equal(await frame.locator('#errors').count(),0,await frame.locator('body').innerText());
    for(const amount of ['2500.10','0.20'])await record('costs',{category:'TRAVEL',amount,date:'2026-09-12',source:'Demo interview response'});
    for(const [category,state] of [['MEDICATION_LIST','PRESENT'],['DIAGNOSTIC_RESULTS','PENDING'],['IMAGING_REPORTS','MISSING']]){
      await go(visit+'/reviews');for(const [name,value]of Object.entries({category,state,text:'Demo reviewer',time:'2026-09-12T10:30',note:'Fictional review'}))await set(name,value);await submit();
      assert.equal(await frame.locator('#errors').count(),0,await frame.locator('body').innerText());
    }
    const body=await bodyText();assert.match(body,/2,500\.30/);assert.match(body,/Demo interview response/);
    assert.equal(await frame.locator('.review-row').count(),5);assert.equal(await frame.locator('.review-row h3').evaluateAll(items=>new Set(items.map(item=>item.textContent)).size),5);
    assert.equal(await frame.locator('html').getAttribute('dir'),lang==='en'?'ltr':'rtl');
    assert.ok(!body.includes('[Missing translation:'));
    await go(visit+'/costs/new');for(const [name,value]of Object.entries({category:'TRAVEL',amount:'-1',date:'2026-09-12'}))await set(name,value);await submit();assert.ok(await frame.locator('#errors').count());
    await go(visit);assert.match(await bodyText(),/2,500\.30/);

    const earlier=await paper('Earlier Demo Clinic','2026-08-01','Earlier.pdf');
    await go('/patients/'+patient+'/print?preview=yes&visit='+visit.split('/').pop()+'&visit='+earlier.split('/').pop()+'&costs=yes');
    await frame.waitForFunction(()=>document.documentElement.dataset.reportReady==='yes');
    const report=await frame.locator('body').innerText();assert.ok(report.indexOf('Earlier Demo Clinic')<report.indexOf('Later Demo Clinic'));assert.match(report,/2,500\.30/);
    assert.equal(await frame.locator('#report-print').isEnabled(),true);
    assert.match(report,/Historical Demo medicine/);assert.match(report,/Fictional prior history/);
    assert.ok((await frame.locator('footer.report-note').innerText()).length>50);if(lang==='en')assert.match(report,/Historical entries do not confirm current treatment/);
    const doc=await frame.locator('.document-appendix').count();assert.equal(doc,0,'Unselected originals should stay out of the report');
    await frame.locator('body').screenshot({path:'tmp/iphone-journey-'+(process.env.BROWSER_ENGINE||'chromium')+'-'+lang+'.png'});

    // Recover an unfinished entry after a true cold runtime restart.
    await go('/documents/new');await set('mode','new');await set('name','Unfinished Journey '+lang);await submit('[name=intent][value=save_later]');
    await page.reload();await ready(page);frame=page.frames()[1];
    const resume=frame.locator('a[href*="unfinished="]').first();assert.ok(await resume.count());await resume.click();
    await page.waitForFunction(()=>document.querySelector('#app').contentDocument?.querySelector('[name=unfinished_id]')?.value);
    frame=page.frames()[1];assert.equal(await frame.locator('[name=name]').inputValue(),'Unfinished Journey '+lang);
    assert.equal(await frame.locator('[name=file]').inputValue(),'');

    // Patient correction, visit removal and restoration use the existing services.
    await go('/patients/'+patient+'/edit');await set('name','Amina Corrected '+lang);await submit();assert.match(await frame.locator('body').innerText(),/Amina Corrected/);
    await go(earlier+'/delete');await frame.locator('[name=confirm]').check();await submit('form button');
    const candidates=await frame.locator('main a[href*="restore"]').evaluateAll(items=>items.map(item=>item.getAttribute('href')));
    const target=candidates.find(url=>url.includes('/removed/'));
    assert.ok(target,'Removed visit has no restore action');frame=await navigate(page,new URL(target,site.base).href);
    await frame.locator('[name=confirm]').check();await submit('form button');
    await go(earlier);assert.match(await frame.locator('body').innerText(),/Earlier Demo Clinic/);

    await go('/patients/new');await set('name','Other Journey '+lang);await set('language','ENGLISH');await submit();
    const identities=await frame.locator('a[href*="/patients/PT-"]').evaluateAll(items=>items.map(item=>/\/patients\/(PT-[^/?]+)(?:\?|$)/.exec(item.getAttribute('href'))?.[1]).filter(Boolean));
    const other=identities.find(id=>id!==patient);assert.ok(other);
    for(const target of [other,patient]){await go(visit+'/edit');await set('patient_id',target);await submit();assert.equal(await frame.locator('#errors').count(),0);}
    await go(earlier+'/delete');await frame.locator('[name=confirm]').check();await submit('form button');
    const permanent=await frame.locator('main a[href*="/permanent"]').first().getAttribute('href');frame=await navigate(page,new URL(permanent,site.base).href);
    await frame.locator('[name=confirm]').check();await submit('form button');assert.equal(await frame.locator('main a[href*="/permanent"]').count(),0);

    // Invalid archives and rejected originals leave confirmed visits usable.
    await go('/passports/import');await frame.locator('[name=archive]').setInputFiles({name:'Damaged.zip',mimeType:'application/zip',buffer:Buffer.from('invalid archive')});await submit('[name=intent][value=check]');assert.ok(await frame.locator('[role=alert]').count());
    await go(visit+'/attachments/new');await frame.locator('[name=file]').setInputFiles({name:'False.pdf',mimeType:'application/pdf',buffer:Buffer.from('not PDF')});await submit();assert.ok(await frame.locator('#errors').count());
    await go(visit);assert.match(await bodyText(),/2,500\.30/);
    await page.reload();await ready(page);await go('/patients');assert.match(await frame.locator('body').innerText(),/Amina Corrected/);
    assert.ok(requests.every(r=>{const url=new URL(r.url),mount='/sehatraasta/iphone/app';const medical=url.pathname===mount||url.pathname.startsWith(mount+'/');return r.method==='GET'&&!r.body&&(!medical||url.pathname.startsWith(mount+'/static/'));}),JSON.stringify(requests.filter(r=>r.method!=='GET')));
    console.log(lang+': all structured types, exact total, reviews, multi-visit report, unfinished reopen, correction/recovery, invalid inputs, no record network requests');
  }catch(error){console.error(lang,error.stack);throw error;}
  finally{await context.close();await site.network(true);}
});
