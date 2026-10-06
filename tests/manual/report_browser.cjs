// Run only against tests/manual/report_demo.py's isolated fictional server.
const {chromium} = require('playwright');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

(async () => {
  const base = process.argv[2] || 'http://127.0.0.1:5091';
  const output = process.argv[3] || 'tmp/report-browser';
  fs.mkdirSync(output, {recursive:true});
  const channel = process.env.SR_BROWSER_CHANNEL || 'msedge';
  const browser = await chromium.launch({...(channel==='chromium'?{}:{channel}), headless:true});
  const page = await browser.newPage();
  const evidence = [];
  const errors = [];
  page.on('pageerror', error => errors.push(error.message));
  const selector = base+'/patients/PK-001/print';
  const preview = selector+'?lang=en&selection=individual&preview=yes&visit=RB-001&document=AT-001';
  try {
    for(const width of [360,768,1280]) for(const lang of ['en','ur','ps']) {
      await page.setViewportSize({width,height:800});
      await page.goto(selector+'?lang='+lang);
      assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true);
      assert.equal(await page.locator('html').getAttribute('dir'),lang==='en'?'ltr':'rtl');
      assert.equal(await page.locator('input:checked').count(),0);
      assert.equal(await page.locator('[name=document]').count(),3);
      assert.equal(await page.locator('.report-choice').evaluateAll(xs=>xs.every(x=>x.getBoundingClientRect().height>=48)),true);
      evidence.push({width,lang,overflow:false,rowsAtLeast48:true});
    }
    // Language changes retain current unsaved checkbox choices, not only the URL.
    await page.goto(selector+'?lang=en');
    await page.locator('[name=visit]').nth(0).check();
    await page.locator('[name=visit]').nth(1).check();
    await page.locator('[name=document]').nth(0).check();
    await page.locator('[name=document]').nth(2).check();
    await page.locator('[name=costs]').check();
    for (const lang of ['ur','ps','en']) {
      await page.locator('.language-nav a[lang='+lang+']').click();
      assert.equal(await page.locator('[name=visit]:checked').count(),2);
      assert.equal(await page.locator('[name=document]:checked').count(),2);
      assert.equal(await page.locator('[name=costs]').isChecked(),true);
    }
    await page.goto(selector+'?lang=en');
    await page.locator('[name=visit]').first().focus();
    await page.keyboard.press('Space'); await page.keyboard.press('Tab');
    assert.equal(await page.evaluate(()=>document.activeElement.name),'document');
    await page.keyboard.press('Space');
    await page.getByRole('button',{name:'Preview record'}).click();
    await page.waitForFunction(()=>document.documentElement.dataset.reportReady==='yes');
    assert.equal(await page.locator('[data-document]').count(),1);
    assert.equal(await page.locator('.document-pages img').count(),1);
    assert.equal(await page.locator('.report-toolbar a,.report-toolbar button,.report-original').evaluateAll(xs=>xs.filter(x=>!x.hidden).every(x=>x.getBoundingClientRect().height>=48)),true);
    await page.reload();
    await page.waitForFunction(()=>document.documentElement.dataset.reportReady==='yes');
    await page.getByRole('link',{name:'Choose visits for PDF'}).click();
    assert.equal(await page.locator('[name=visit]:checked').count(),1);
    assert.equal(await page.locator('[name=document]:checked').count(),1);
    await page.goBack();
    await page.waitForFunction(()=>document.documentElement.dataset.reportReady==='yes');
    for(let i=0;i<2;i++) {await page.goto(preview); await page.waitForFunction(()=>document.documentElement.dataset.reportReady==='yes');}
    await page.emulateMedia({media:'print'});
    assert.equal(await page.locator('.report-original').evaluate(x=>getComputedStyle(x).display),'none');
    assert.equal(await page.evaluate(()=>getComputedStyle(document.body).backgroundColor),'rgb(255, 255, 255)');
    await page.pdf({path:path.join(output,'selected-original.pdf'),format:'A4',preferCSSPageSize:true,displayHeaderFooter:false});
    await page.emulateMedia({media:'screen'});
    // Failed local fetch cannot be presented as a successful complete report.
    await page.route('**/attachments/AT-001/content', route=>route.abort());
    await page.reload();
    await page.waitForFunction(()=>document.documentElement.dataset.reportError);
    assert.ok((await page.locator('#report-status').innerText()).includes('fictional-document-1.png'));
    assert.equal(await page.locator('#report-print').isDisabled(),true);
    assert.equal(await page.locator('#report-retry').isVisible(),true);
    await page.unroute('**/attachments/AT-001/content');
    await page.locator('#report-retry').click();
    await page.waitForFunction(()=>document.documentElement.dataset.reportReady==='yes');
    assert.equal(await page.locator('#report-print').isEnabled(),true);
    // A stalled document must reach a bounded retry state, not load forever.
    await page.route('**/attachments/AT-001/content', async route=>{
      await new Promise(resolve=>setTimeout(resolve,45000));
      try {await route.continue();} catch (_) { /* request cancelled by timeout */ }
    });
    await page.reload();
    await page.waitForFunction(()=>document.documentElement.dataset.reportError==='AbortError',null,{timeout:35000});
    assert.ok((await page.locator('#report-status').innerText()).includes('took too long'));
    assert.equal(await page.locator('#report-print').isDisabled(),true);
    await page.unroute('**/attachments/AT-001/content');
    await page.locator('#report-retry').click();
    await page.waitForFunction(()=>document.documentElement.dataset.reportReady==='yes');
    // Ownership, duplicates, empty input, long forged input remain safe.
    await page.goto(selector+'?preview=yes&selection=individual&lang=en');
    assert.ok((await page.locator('#errors').innerText()).includes('Choose at least one visit'));
    assert.equal(await page.evaluate(()=>document.activeElement.id),'errors');
    for(const query of ['preview=yes&selection=individual',
      'preview=yes&selection=individual&visit=RB-004',
      'preview=yes&selection=individual&visit=RB-001&document=AT-004',
      'preview=yes&selection=individual&visit=RB-001&document=AT-001&document=AT-001',
      'preview=yes&selection=individual&visit='+('x'.repeat(2000))]) {
      assert.equal((await page.goto(selector+'?'+query)).status(),422);
      assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true);
    }
    await page.goto(selector+'?selection=individual&preview=yes&visit=RB-003');
    await page.waitForFunction(()=>document.documentElement.dataset.reportReady==='yes');
    assert.equal(await page.locator('[data-document]').count(),0);
    assert.equal(await page.locator('#report-print').isEnabled(),true);
    await page.goto(selector);
    await page.setViewportSize({width:360,height:800});
    await page.screenshot({path:path.join(output,'selector-360.png'),fullPage:true});
    assert.deepEqual(errors,[]);
    fs.writeFileSync(path.join(output,'evidence.json'),JSON.stringify({layouts:evidence,
      passed:['keyboard','focused actionable error','48px preview controls','retained selection','unsaved language switch','refresh','back','repeated preview','white A4',
        'excluded originals','failed-fetch print blocking','named failure','retry','stalled-fetch timeout',
        'ownership','empty','duplicate','long input'],pageErrors:errors},null,2));
    console.log('PASS: selective report hostile browser checks; evidence in '+output);
  } finally {await browser.close();}
})().catch(error=>{console.error(error);process.exitCode=1;});
