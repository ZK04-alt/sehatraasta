// Synthetic preview only. Run with SR_TEST_URL pointing to the isolated test server.
const {chromium} = require('playwright');
const assert = require('assert');
const fs = require('fs');
const path = require('path');
const base = process.env.SR_TEST_URL || 'http://127.0.0.1:8769';
const output = process.env.SR_TEST_OUTPUT || 'tmp/forms-review-20260925';
(async () => {
  const browser = await chromium.launch({channel:'msedge', headless:true});
  const report = {checks:[], pageErrors:[], externalRequests:[]};
  try {
    const context = await browser.newContext({viewport:{width:1440,height:1000}});
    await context.route('**/*', route => {
      if(!route.request().url().startsWith(base + '/')) {
        report.externalRequests.push(route.request().url()); return route.abort();
      }
      return route.continue();
    });
    const page = await context.newPage();
    page.on('pageerror', e => report.pageErrors.push(e.message));
    await page.goto(base + '/bundles/new?lang=en');
    assert.equal(await page.locator('[data-record-section]:not([open])').count(), 6);
    assert.equal(await page.locator('[data-preset] select').evaluateAll(items => items.every(item => item.value==='')), true);
    await page.screenshot({path:path.join(output,'compact-intake-desktop.png'),fullPage:true});
    await page.locator('#birth_year').fill('1980');
    await page.locator('[data-year-picker] summary').focus();
    await page.keyboard.press('Enter');
    await page.locator('[data-years-back]').click();
    assert.equal(await page.locator('[data-year-range]').innerText(),'1968–1979');
    await page.locator('[data-years-next]').click();
    await page.locator('[data-year-grid] button', {hasText:'1984'}).focus();
    await page.keyboard.press('Enter');
    assert.equal(await page.locator('#birth_year').inputValue(),'1984');
    assert.equal(await page.evaluate(()=>document.activeElement.id),'birth_year');
    assert.equal(await page.locator('[data-year-picker]').getAttribute('open'),null);
    report.checks.push('Year-only calendar: decade navigation and keyboard selection');
    for(const lang of ['en','ur','ps']) {
      await page.goto(base+'/bundles/new?lang='+lang);
      await page.setViewportSize({width:320,height:900});
      await page.locator('[data-year-picker] summary').click();
      assert(await page.evaluate(()=>document.documentElement.scrollWidth<=320));
      assert(!(await page.locator('body').innerText()).includes('[Missing translation:'));
      await page.screenshot({path:path.join(output,'year-picker-'+lang+'-320.png'),fullPage:true});
    }
    report.checks.push('320px year picker and form in English, Urdu and Pashto');
    await page.setViewportSize({width:1440,height:1000});
    await page.goto(base+'/bundles/new?patient_id=PK-001&lang=en');
    await page.locator('#source_facility').fill('Demo clinic');
    await page.locator('[data-repeat=medications] .record-summary').click();
    await page.locator('#medications-0-name').fill('Fictional medicine');
    await page.locator('#medications-0-strength').selectOption('10 mg');
    await page.locator('#medications-0-dose').selectOption('__custom__');
    assert(await page.locator('#medications-0-dose-custom').isVisible());
    await page.locator('#medications-0-dose-custom').fill('Original custom example');
    await page.locator('#medications-0-frequency').selectOption('Twice a day');
    await page.locator('#medications-0-duration').selectOption('7 days');
    await Promise.all([page.waitForNavigation(),page.locator('button[value=save]').click()]);
    assert(await page.locator('#errors a[href="#destination"]').count());
    assert(await page.locator('#medications-0-dose-custom').isVisible());
    assert.equal(await page.locator('#medications-0-dose-custom').inputValue(),'Original custom example');
    assert.equal(await page.locator('[data-repeat=medications] [data-record-section]').getAttribute('open'),'');
    await page.locator('#destination').fill('Demo district hospital');
    await page.locator('[data-repeat=costs] .record-summary').click();
    await page.locator('#costs-0-category').selectOption('TRAVEL');
    await page.locator('#costs-0-amount').fill('2500.10');
    await page.locator('#costs-0-date').fill('2026-09-25');
    await page.screenshot({path:path.join(output,'medicine-presets-desktop.png'),fullPage:true});
    await Promise.all([page.waitForNavigation(),page.locator('button[value=save]').click()]);
    assert(!page.url().includes('/new'));
    await page.reload();
    const saved = await page.locator('main').innerText();
    assert(saved.includes('Original custom example'));
    assert(saved.includes('2,500.10'));
    assert(saved.includes('source not supplied'));
    report.checks.push('Preset/custom medicine and cost saved without source, route or instructions; retained after reload');
    const noJS = await browser.newContext({javaScriptEnabled:false});
    const simple = await noJS.newPage();
    await simple.goto(base+'/bundles/new?patient_id=PK-001&lang=en');
    await simple.locator('#source_facility').fill('Demo clinic');
    await simple.locator('#destination').fill('Demo hospital');
    await simple.locator('[data-repeat=medications] .record-summary').click();
    await simple.locator('#medications-0-name').fill('No JS demo');
    for (const [key,value] of Object.entries({strength:'Custom strength',dose:'Custom dose',frequency:'Custom frequency',duration:'Custom duration'})) {
      await simple.locator('#medications-0-'+key).selectOption('__custom__');
      await simple.locator('#medications-0-'+key+'-custom').fill(value);
    }
    await Promise.all([simple.waitForNavigation(),simple.locator('button[value=save]').click()]);
    assert(!simple.url().includes('/new'));
    assert((await simple.locator('main').innerText()).includes('Custom strength'));
    report.checks.push('No-JavaScript custom entry and optional collapsed sections save successfully');
    await noJS.close();
    assert.deepEqual(report.pageErrors,[]);
    assert.deepEqual(report.externalRequests,[]);
    fs.writeFileSync(path.join(output,'optional-form-results.json'),JSON.stringify(report,null,2));
    console.log(JSON.stringify(report));
  } finally { await browser.close(); }
})().catch(error=>{console.error(error);process.exitCode=1;});
