// Isolated fictional browser checks. Pass a URL and optional output folder.
const {chromium} = require('playwright');
const assert = require('node:assert/strict');
const path = require('node:path');

(async () => {
  const base = process.argv[2] || 'http://127.0.0.1:5068';
  const output = process.argv[3] || 'tmp/doctor-report-20261005';
  const browser = await chromium.launch({channel:'msedge', headless:true});
  const page = await browser.newPage({viewport:{width:1100,height:800}});
  const errors = [];
  page.on('pageerror', error => errors.push(error.message));
  try {
    await page.goto(base+'/patients');
    assert.ok((await page.locator('body').innerText()).includes('Amina Demo'));
    assert.ok(!(await page.locator('body').innerText()).includes('PK-001'));
    await page.goto(base+'/patients/PK-001/print');
    for(const choice of await page.locator('[name=visit]').all()) await choice.check();
    for(const choice of await page.locator('[name=document]').all()) await choice.check();
    await page.locator('form.entry-form button').click();
    await page.waitForFunction(()=>document.documentElement.dataset.reportReady==='yes');
    assert.equal(await page.locator('.report-visit').count(),3);
    assert.equal(await page.locator('.document-page img').count(),3);
    assert.equal(await page.locator('.document-pages > img').count(),0);
    const visible = await page.locator('body').innerText();
    for(const text of ['Not recorded','PK-001','RB-001','source not supplied']) assert.ok(!visible.includes(text),text);
    assert.equal(await page.evaluate(()=>getComputedStyle(document.body).backgroundColor),'rgb(255, 255, 255)');
    assert.ok(visible.includes('Medicine name'));
    assert.ok(visible.includes('Prepared on'));
    await page.setViewportSize({width:360,height:800});
    await page.emulateMedia({media:'print'});
    assert.equal(await page.locator('.doctor-report').evaluate(el=>getComputedStyle(el).padding),'0px');
    assert.equal(await page.locator('.report-fields').first().evaluate(el=>getComputedStyle(el).display),'table');
    assert.equal(await page.locator('.report-fields th').first().evaluate(el=>getComputedStyle(el).display),'table-cell');
    for (const header of await page.locator('.visit-heading').all()) {
      assert.equal(await header.evaluate(el=>el.querySelector('.report-qr').getBoundingClientRect().right<=el.getBoundingClientRect().right+1),true,'QR overflow');
    }
    await page.pdf({path:path.join(output,'browser-verified-record.pdf'),format:'A4',printBackground:false,preferCSSPageSize:true,displayHeaderFooter:false});
    // Layout stress only: clone fictional DOM content, not stored patient data.
    await page.evaluate(()=>{
      document.querySelectorAll('.document-appendix').forEach(el=>el.remove());
      const visits = [...document.querySelectorAll('.report-visit')];
      const note = document.querySelector('.report-note');
      for(let round=0; round<5; round++) for(const visit of visits) note.before(visit.cloneNode(true));
    });
    await page.pdf({path:path.join(output,'long-record-layout-check.pdf'),format:'A4',printBackground:false,preferCSSPageSize:true,displayHeaderFooter:false});
    await page.emulateMedia({media:'screen'});
    for(const lang of ['en','ur','ps']) {
      await page.setViewportSize({width:360,height:800});
      await page.goto(base+'/patients/PK-001/print?lang='+lang);
      assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true,lang+' selection overflow');
      await page.goto(base+'/sharing?lang='+lang);
      assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true,lang+' help overflow');
    }
    await page.goto(base+'/bundles/RB-003/delete?lang=en');
    await page.getByRole('link',{name:'Cancel',exact:true}).click();
    assert.ok((await page.locator('body').innerText()).includes('Karachi specialist'));
    await page.goto(base+'/bundles/RB-001/attachments/new');
    await page.locator('[name=file]').setInputFiles({name:'broken.pdf',mimeType:'application/pdf',buffer:Buffer.from('%PDF-1.4\nnot a readable PDF')});
    await page.locator('[name=category]').selectOption('OTHER');
    await page.locator('[name=date]').fill('2026-10-05');
    await page.locator('[name=source_type]').selectOption('NOT_SUPPLIED');
    await page.locator('button[name=intent][value=save]').click();
    await page.waitForURL(/\/bundles\/RB-001\?/);
    await page.goto(base+'/bundles/RB-001/print');
    await page.waitForFunction(()=>document.querySelector('#report-status').getAttribute('role')==='alert');
    assert.equal(await page.locator('#report-print').isDisabled(),true);
    await page.goto(base+'/bundles/RB-001');
    const attachment = page.locator('.attachment-row').filter({hasText:'broken.pdf'});
    await attachment.getByRole('link',{name:'Delete',exact:true}).click();
    await page.locator('[name=confirm]').check();
    await page.locator('button[name=intent][value=save]').click();
    await page.waitForURL(/\/bundles\/RB-001\?/);
    assert.deepEqual(errors,[]);
    console.log('PASS: white A4 PDF from 360px viewport, unclipped QR, specific labels, multi-visit PDF, documents, mobile EN/UR/PS, cancel deletion, unreadable PDF blocks print.');
  } finally { await browser.close(); }
})().catch(error=>{console.error(error);process.exitCode=1;});
