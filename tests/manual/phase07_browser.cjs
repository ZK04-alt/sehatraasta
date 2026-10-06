// Run against the isolated Phase 7 demo, not a working dataset.
const { chromium } = require('playwright');
const fs = require('fs');
const path = require('path');
const assert = require('assert');

(async () => {
  const base = process.env.SR_TEST_URL || 'http://127.0.0.1:8767';
  const output = path.resolve(process.env.SR_TEST_OUTPUT || 'tmp/phase07-browser');
  fs.mkdirSync(output, {recursive:true});
  const browser = await chromium.launch({channel:'msedge', headless:true});
  const result = {pages:0, externalRequests:[], consoleErrors:[], screenshots:[],
    zoom:'200% CSS zoom simulation; native browser zoom and Narrator need human review'};
  try {
    const context = await browser.newContext({viewport:{width:1440,height:1000}});
    await context.route('**/*', route => {
      const url = route.request().url();
      if (!url.startsWith(base + '/')) { result.externalRequests.push(url); return route.abort(); }
      return route.continue();
    });
    const page = await context.newPage();
    page.on('pageerror', error => result.consoleErrors.push(error.message));
    const paths = ['/bundles', '/patients', '/patients/new', '/bundles/new', '/bundles/SR-DEMO-001',
      '/bundles/SR-DEMO-002', '/bundles/SR-DEMO-001/costs/new', '/bundles/SR-DEMO-001/attachments/new',
      '/bundles/SR-DEMO-001/reviews', '/restore', '/lookup', '/privacy', '/terms', '/not-found'];
    for (const lang of ['en','ur','ps']) {
      for (const width of [1440,320]) {
        await page.setViewportSize({width,height:1000});
        for (const route of paths) {
          await page.goto(base + route + '?lang=' + lang);
          assert.equal(await page.locator('html').getAttribute('dir'), lang==='en'?'ltr':'rtl');
          const overflow = await page.evaluate(() => document.documentElement.scrollWidth > document.documentElement.clientWidth + 1);
          assert(!overflow, `Horizontal overflow ${lang} ${width} ${route}`);
          assert(!(await page.locator('body').innerText()).includes('[Missing translation:'));
          assert(await page.evaluate(() => [...document.querySelectorAll('label')].every(el => document.getElementById(el.htmlFor))));
          result.pages++;
        }
      }
    }
    await page.setViewportSize({width:1440,height:1000});
    // A user chooses a patient, never enters or invents a new bundle ID.
    await page.goto(base + '/bundles/new?patient_id=PK-001&lang=en');
    assert.equal(await page.locator('input[name=ID]').count(), 0);
    assert(await page.locator('#creation_time').inputValue());
    const patientOptions = await page.locator('#patient_id option').evaluateAll(items => items.map(item => item.value).filter(Boolean));
    assert(patientOptions.length);
    await page.locator('#patient_id').selectOption(patientOptions[0]);
    await page.locator('#source_facility').fill('Demo BHU');
    await page.locator('#destination').fill('Demo District Hospital');
    await page.screenshot({path:path.join(output,'new-bundle.png'),fullPage:true});
    await Promise.all([page.waitForNavigation(), page.locator('button[value=save]').click()]);
    assert(/\/bundles\/SR-[A-Z]{12}-[0-9]{3}\?/.test(page.url()));
    assert((await page.locator('main').innerText()).includes('Demo District Hospital'));
    await page.reload();
    assert((await page.locator('main').innerText()).includes('Demo District Hospital'));
    result.automaticBundle = 'Created without an ID field, redirected to generated ID, retained after reload';
    for (const [route,name] of [['/bundles?lang=en','desktop-queue'],['/bundles/SR-DEMO-001?lang=en','desktop-bundle'],['/bundles/SR-DEMO-002?lang=ur','urdu-long-text']]) {
      await page.goto(base + route);
      await page.screenshot({path:path.join(output,name+'.png'),fullPage:true});
      result.screenshots.push(name+'.png');
    }
    // Language changes preserve unsaved original text and do not insert records.
    await page.goto(base + '/patients/new?lang=en');
    await page.locator('#name').fill('Original مثال ABC-123');
    await page.locator('#lang').selectOption('ur');
    await Promise.all([page.waitForNavigation(),page.locator('button[value=language]').click()]);
    assert.equal(await page.locator('#name').inputValue(),'Original مثال ABC-123');
    assert.equal(await page.locator('html').getAttribute('dir'),'rtl');
    // Server rejection with summary focus and keyboard link to the bad amount.
    await page.goto(base + '/bundles/SR-DEMO-001/costs/new?lang=en');
    for (const [key,value] of Object.entries({amount:'-1',date:'2026-09-21',source:'Demo source',source_type:'reported',source_identifier:'DEMO-099'})) await page.locator('#'+key).fill(value);
    await page.locator('#category').selectOption('TRAVEL');
    await Promise.all([page.waitForNavigation(),page.locator('button[value=save]').click()]);
    assert.equal(await page.evaluate(()=>document.activeElement.id),'errors');
    await page.keyboard.press('Tab');
    assert.equal(await page.evaluate(()=>document.activeElement.getAttribute('href')),'#amount');
    await page.keyboard.press('Enter');
    assert.equal(await page.evaluate(()=>document.activeElement.id),'amount');
    await page.setViewportSize({width:320,height:900});
    await page.screenshot({path:path.join(output,'invalid-cost-320.png'),fullPage:true});
    await page.setViewportSize({width:640,height:1000});
    await page.evaluate(()=>document.documentElement.style.zoom='2');
    assert(await page.evaluate(()=>document.documentElement.scrollWidth<=document.documentElement.clientWidth+1));
    result.errorFocus = 'Summary to amount by keyboard';
    // Complete a patient submission by keyboard only after opening the page.
    await page.goto(base + '/patients?lang=en');
    await page.goto(base + '/patients/new?lang=en');
    await page.setViewportSize({width:1440,height:1000});
    for(let i=0;i<30 && await page.evaluate(()=>document.activeElement.id)!=='name';i++) await page.keyboard.press('Tab');
    assert.equal(await page.evaluate(()=>document.activeElement.id),'name');
    assert.equal(await page.locator('#name').evaluate(el=>getComputedStyle(el).outlineWidth),'3px');
    await page.keyboard.type('Keyboard Demo'); await page.keyboard.press('Tab');
    await page.keyboard.type('1980');
    for(let i=0;i<10 && await page.evaluate(()=>document.activeElement.id)!=='language';i++) await page.keyboard.press('Tab');
    assert.equal(await page.evaluate(()=>document.activeElement.id),'language');
    await page.keyboard.press('ArrowDown'); await page.keyboard.press('Tab');
    await Promise.all([page.waitForURL('**/patients?*'),page.keyboard.press('Enter')]);
    assert((await page.locator('main').innerText()).includes('Keyboard Demo'));
    assert(/PT-[2-9A-HJ-NP-Z]{6}/.test(await page.locator('main').innerText()));
    assert(await page.locator('[role=status]').count());
    result.keyboard = 'Patient created using Tab, typing, arrows and Enter with visible focus';
    // Simulate the submit event without navigation to inspect the transient UI.
    await page.goto(base + '/patients/new?lang=en');
    await page.locator('#name').fill('Loading Demo');
    await page.locator('#birth_year').fill('1980'); await page.locator('#language').selectOption('ENGLISH');
    const loading = await page.evaluate(()=>{
      const form = document.querySelector('.entry-form');
      form.addEventListener('submit', event=>event.preventDefault(), {once:true});
      form.requestSubmit(form.querySelector('button[value=save]'));
      return {visible:!form.querySelector('.submission').hidden,busy:form.getAttribute('aria-busy')};
    });
    assert(loading.visible); assert.equal(loading.busy,'true');
    result.loading = 'Simulated submit event displays status and static skeleton; no save in this state check';
    // Download comes from the real export service.
    await page.goto(base + '/bundles/SR-DEMO-001?lang=en');
    const [download] = await Promise.all([page.waitForEvent('download'),page.locator('form[data-download] button').click()]);
    await download.saveAs(path.join(output,'synthetic-export.json'));
    assert(JSON.parse(fs.readFileSync(path.join(output,'synthetic-export.json'),'utf8')));
    // Print has no navigation, with the existing opaque QR content.
    await page.goto(base + '/bundles/SR-DEMO-001/print?lang=en');
    await page.emulateMedia({media:'print'});
    assert.equal(await page.locator('.sidebar').evaluate(el=>getComputedStyle(el).display),'none');
    await page.locator('.qr').screenshot({path:path.join(output,'rendered-qr.png')});
    await page.pdf({path:path.join(output,'synthetic-print.pdf'),format:'A4',printBackground:true});
    await page.screenshot({path:path.join(output,'print.png'),fullPage:true});
    await page.emulateMedia({media:'screen'});
    // The server-rendered workflow also works without JavaScript.
    const noJs = await browser.newContext({javaScriptEnabled:false});
    const simple = await noJs.newPage();
    await simple.goto(base + '/bundles/SR-DEMO-001/edit?lang=en');
    await simple.locator('#destination').fill('Demo District Hospital - Orthopaedics');
    await Promise.all([simple.waitForNavigation(),simple.locator('button[value=save]').click()]);
    assert((await simple.locator('main').innerText()).includes('Record saved.'));
    result.withoutJavaScript = 'Edit saved and redirected';
    await noJs.close();
    assert.deepEqual(result.externalRequests,[]);
    assert.deepEqual(result.consoleErrors,[]);
    fs.writeFileSync(path.join(output,'results.json'),JSON.stringify(result,null,2));
    console.log(JSON.stringify(result));
  } finally { await browser.close(); }
})().catch(error=>{console.error(error);process.exitCode=1;});
