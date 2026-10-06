// Only run against the separate synthetic test server; never a working instance.
const {chromium} = require('playwright');
const fs = require('fs');
const path = require('path');
const assert = require('assert');
const base = process.env.SR_TEST_URL || 'http://127.0.0.1:8768';
const output = path.resolve(process.env.SR_TEST_OUTPUT || 'tmp/intake-review-20260923');
const sections = ['medications', 'orders', 'results', 'imaging', 'instructions', 'costs'];

(async () => {
  fs.mkdirSync(output, {recursive:true});
  const browser = await chromium.launch({channel:'msedge', headless:true});
  const result = {modes:[], noJavaScript:[], rows:[], externalRequests:[], pageErrors:[], cspViolations:[]};
  try {
    const context = await browser.newContext({viewport:{width:1440,height:1000}});
    await context.route('**/*', route => {
      if (!route.request().url().startsWith(base + '/')) {
        result.externalRequests.push(route.request().url());
        return route.abort();
      }
      return route.continue();
    });
    await context.exposeBinding('reportCsp', (_, value) => result.cspViolations.push(value));
    await context.addInitScript(() => document.addEventListener('securitypolicyviolation', e => window.reportCsp(e.violatedDirective)));
    const page = await context.newPage();
    page.on('pageerror', e => result.pageErrors.push(e.message));
    async function fill(fields, prefix='') {
      for (const [name, value] of Object.entries(fields)) {
        const input = page.locator('[name="' + prefix + name + '"]');
        await input.evaluate(el => { const group=el.closest('[data-record-section]'); if(group) group.open=true; });
        if (await input.evaluate(el => el.tagName === 'SELECT')) {
          const choices = await input.locator('option').evaluateAll(options => options.map(option => option.value));
          if (!choices.includes(value) && choices.includes('__custom__')) {
            await input.selectOption('__custom__');
            await page.locator('[name="'+prefix+name+'__custom"]').fill(value);
          } else await input.selectOption(value);
        } else await input.fill(value);
      }
    }
    async function submit() {
      await Promise.all([page.waitForNavigation(), page.locator('button[value=save]').click()]);
    }
    const formValues = () => page.locator('#intake-form').evaluate(form =>
      [...new FormData(form)].filter(([key]) => !['csrf','had_errors','lang','unfinished_id','unfinished_revision'].includes(key)));
    await page.goto(base + '/bundles/new?lang=en');
    assert.equal(await page.locator('h1').innerText(), 'New visit');
    await fill({name:'Combined Demo مثال',birth_year:'1980',language:'URDU',
      source_facility:'Demo BHU',destination:'Demo Hospital'});
    for (const section of sections) {
      const group = page.locator('[data-repeat="'+section+'"]');
      await group.locator('.record-summary').click();
      await group.locator('[data-add-row]').click();
      assert.equal(await group.locator('[data-rows] > [data-row]').count(),2);
      assert((await page.evaluate(() => document.activeElement.name)).startsWith(section+'.1.'));
      await group.locator('[data-row="1"] [data-remove-row]').click();
      assert.equal(await group.locator('[data-rows] > [data-row]').count(),1);
      result.rows.push(section + ': add/remove/focus');
    }
    const medication = {name:'Demo medicine',strength:'Verbatim',dose:'Verbatim',route:'Verbatim',
      frequency:'Verbatim',duration:'Verbatim',instructions:'Original مثال ABC-123',source:'Demo sheet'};
    await fill(medication,'medications.0.');
    await page.locator('[data-repeat="medications"] [data-add-row]').click();
    // Removed row key 1 is never reused in this page session.
    await fill({...medication,name:'Second demo',dose:''},'medications.2.');
    await fill({name:'Demo test',date:'2026-09-22',source:'Demo sheet',workflow_status:'ORDERED'},'orders.0.');
    await page.locator('[data-repeat="orders"] [data-add-row]').click();
    await fill({name:'Demo test',date:'2026-09-22',source:'Second sheet',workflow_status:'ORDERED'},'orders.2.');
    await fill({name:'Demo result',date:'2026-09-22',source:'Demo sheet',interpretation:'Original result',order_key:'2'},'results.0.');
    await fill({modality:'X-ray',body_part:'Demo part',date:'2026-09-22',facility:'Demo clinic',report:'Original report'},'imaging.0.');
    await fill({category:'Demo',language:'URDU',text:'Original instruction',source:'Demo sheet',date:'2026-09-22'},'instructions.0.');
    await fill({category:'TRAVEL',amount:'2500.00',date:'2026-09-22',source:'Demo source',source_type:'reported',source_identifier:'Demo interview'},'costs.0.');
    const before = await formValues();
    await submit();
    assert.equal(await page.evaluate(() => document.activeElement.id), 'errors');
    assert.deepEqual(await formValues(), before);
    await page.locator('#errors a[href="#medications-2-dose"]').click();
    assert.equal(await page.evaluate(() => document.activeElement.id),'medications-2-dose');
    await page.locator('#lang').selectOption('ur');
    await Promise.all([page.waitForNavigation(),page.locator('button[value=language]').click()]);
    assert.deepEqual(await formValues(),before);
    assert.equal(await page.locator('html').getAttribute('dir'),'rtl');
    await page.setViewportSize({width:320,height:900});
    assert(await page.evaluate(()=>document.documentElement.scrollWidth<=320));
    await page.screenshot({path:path.join(output,'intake-error-rtl-320.png'),fullPage:true});
    await page.setViewportSize({width:1440,height:1000});
    await page.screenshot({path:path.join(output,'intake-filled-rtl.png'),fullPage:true});
    await fill({dose:'Corrected demo dose'},'medications.2.');
    await submit();
    assert(/\/bundles\/SR-[A-Z]{12}-\d{3}\?/.test(page.url()));
    result.modes.push('new: all sections, two medications/orders, preserved error state and RTL switch');
    const bundleUrl = page.url().split('?')[0];
    await page.goto(bundleUrl + '/attachments/new?lang=en');
    assert.equal(await page.locator('input[name=ID]').count(),0);
    await page.locator('#file').setInputFiles({name:'demo.pdf',mimeType:'application/pdf',buffer:Buffer.from('%PDF-1.4\nSynthetic demonstration only: ' + bundleUrl)});
    await fill({category:'OTHER',date:'2026-09-22',source_type:'NOT_SUPPLIED'});
    // Older forms had a separate confirmation; current forms have no such control.
    if (await page.locator('#synthetic').count()) await page.locator('#synthetic').check();
    await submit();
    assert(/AT-[2-9A-HJ-NP-Z]{6}/.test(await page.locator('main').innerText()));
    result.attachment='Follow-up synthetic upload with generated AT identifier';
    await page.goto(base + '/bundles/new?lang=en');
    await fill({name:'Inactive name',birth_year:'-1',language:'ENGLISH'});
    await page.locator('#mode').selectOption('existing');
    await fill({patient_id:'PK-001',source_facility:'Demo BHU',destination:'Existing patient demo'});
    await submit();
    assert(/\/bundles\/SR-[A-Z]{12}-\d{3}\?/.test(page.url()));
    result.modes.push('existing: ignores inactive new-patient values');
    // A removed order link must not be reassigned after an error/round-trip.
    await page.goto(base + '/bundles/new?lang=en');
    await fill({name:'Removed link demo',birth_year:'1980',language:'ENGLISH',source_facility:'Demo',destination:'Demo'});
    await page.locator('[data-repeat=orders] .record-summary').click();
    await page.locator('[data-repeat=orders] [data-add-row]').click();
    await fill({name:'Removed order',date:'2026-09-22',source:'Demo',workflow_status:'ORDERED'},'orders.1.');
    await fill({name:'Linked result',date:'2026-09-22',source:'Demo',interpretation:'Demo',order_key:'1'},'results.0.');
    await page.locator('[data-repeat=orders] [data-row="1"] [data-remove-row]').click();
    await submit();
    assert.equal(await page.locator('#results-0-order_key').inputValue(),'1');
    await page.locator('[data-repeat=orders] .record-summary').click();
    await page.locator('[data-repeat=orders] [data-add-row]').click();
    assert.equal(await page.locator('[data-repeat=orders] [data-row="1"]').count(),0);
    assert.equal(await page.locator('[data-repeat=orders] [data-row="2"]').count(),1);
    assert.equal(await page.locator('#results-0-order_key').inputValue(),'1');
    result.removedOrder='Invalid link retained; newly added order cannot reuse its key after an error';
    for (const mode of ['new','existing']) {
      const noJs = await browser.newContext({javaScriptEnabled:false});
      const simple = await noJs.newPage();
      await simple.goto(base + '/bundles/new?lang=en');
      assert(await simple.locator('[data-patient-mode=new]').isVisible());
      assert(await simple.locator('[data-patient-mode=existing]').isVisible());
      assert(!await simple.locator('[data-repeat=orders] [data-add-row]').isVisible());
      await simple.locator('#mode').selectOption(mode);
      if (mode==='new') {
        await simple.locator('#name').fill('No JavaScript Demo');
        await simple.locator('#birth_year').fill('1980');
        await simple.locator('#language').selectOption('ENGLISH');
      } else await simple.locator('#patient_id').selectOption('PK-001');
      await simple.locator('#source_facility').fill('Demo source');
      await simple.locator('#destination').fill('Demo destination');
      await Promise.all([simple.waitForNavigation(),simple.locator('button[value=save]').click()]);
      assert(/\/bundles\/SR-[A-Z]{12}-\d{3}\?/.test(simple.url()));
      result.noJavaScript.push(mode);
      await noJs.close();
    }
    // Render local SVGs at their actual intended sizes, in a separate inspection page.
    await page.setContent('<p>16px</p><img width="16" height="16" src="'+base+'/static/favicon.svg"><p>32px</p><img width="32" height="32" src="'+base+'/static/favicon.svg"><p>Wordmark</p><img width="268" height="54" src="'+base+'/static/wordmark.svg">');
    await page.locator('img').evaluateAll(images => Promise.all(images.map(image => image.decode())));
    await page.screenshot({path:path.join(output,'local-marks.png')});
    assert.deepEqual(result.externalRequests,[]);
    assert.deepEqual(result.pageErrors,[]);
    assert.deepEqual(result.cspViolations,[]);
    fs.writeFileSync(path.join(output,'intake-results.json'),JSON.stringify(result,null,2));
    console.log(JSON.stringify(result));
  } finally { await browser.close(); }
})().catch(error=>{console.error(error);process.exitCode=1;});
