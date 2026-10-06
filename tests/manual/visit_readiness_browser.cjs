// Run only against the separate fictional test dataset.
const {chromium} = require('playwright');
const assert = require('assert');
const fs = require('fs');
const path = require('path');
const base = process.env.SR_PREVIEW_URL || 'http://127.0.0.1:5067';
const output = path.resolve('tmp/visit-readiness-20261004');
(async () => {
  fs.mkdirSync(output, {recursive:true});
  const browser = await chromium.launch({channel:'msedge', headless:true});
  const result = {workflow:[], largeText:[], errors:[], externalRequests:[]};
  const context = await browser.newContext({viewport:{width:393,height:852}});
  await context.route('**/*', route => {
    if (!route.request().url().startsWith(base + '/')) {result.externalRequests.push(route.request().url()); return route.abort();}
    return route.continue();
  });
  const page = await context.newPage();
  page.on('pageerror', e => result.errors.push(e.message));
  try {
    await page.goto(base + '/bundles/new');
    assert.equal(await page.locator('h1').innerText(), 'New visit');
    assert.equal(await page.locator('[name=status]').count(), 0);
    await page.locator('[name=name]').fill('Leave and Resume Demo');
    await page.locator('[name=source_facility]').fill('Demo Hospital Visit');
    await page.getByRole('status').filter({hasText:'Saved on this device'}).waitFor();
    const resume = page.url();
    assert(resume.includes('unfinished=UV-'));
    // Navigation waits for the latest edit, not only the earlier saved snapshot.
    await page.locator('[name=name]').fill('Leave and Resume Demo Updated');
    await page.locator('.sidebar a[href^="/patients"]').click();
    await page.waitForURL('**/patients?*');
    await page.goto(base + '/bundles');
    assert((await page.locator('main').innerText()).includes('Unfinished'));
    await page.getByRole('link').filter({hasText:'Leave and Resume Demo Updated'}).click();
    assert.equal(await page.locator('[name=name]').inputValue(), 'Leave and Resume Demo Updated');
    result.workflow.push('Autosave and immediate navigation preserve the last edit');
    // Resume from a fresh browser session: no values are retained only in the cookie.
    const second = await browser.newContext({viewport:{width:393,height:852}});
    const reopened = await second.newPage();
    await reopened.goto(resume);
    assert.equal(await reopened.locator('[name=name]').inputValue(), 'Leave and Resume Demo Updated');
    await reopened.locator('[name=birth_year]').fill('1980');
    await reopened.locator('[name=language]').selectOption('URDU');
    await reopened.locator('[data-repeat=medications] .record-summary').click();
    await reopened.locator('[name="medications.0.name"]').fill('Partial Demo Medicine');
    await Promise.all([reopened.waitForURL('**/bundles?*'),reopened.locator('button[value=save_later]').click()]);
    await reopened.getByRole('link').filter({hasText:'Leave and Resume Demo Updated'}).click();
    assert.equal(await reopened.locator('[name="medications.0.name"]').inputValue(),'Partial Demo Medicine');
    await Promise.all([reopened.waitForNavigation(),reopened.locator('button[value=save]').click()]);
    assert(await reopened.locator('#errors').isVisible());
    assert.equal(await reopened.locator('[name="medications.0.name"]').inputValue(),'Partial Demo Medicine');
    result.workflow.push('Incomplete medication saves unfinished; completion shows readable required-field errors');
    await reopened.locator('[name="medications.0.name"]').fill('');
    await Promise.all([reopened.waitForNavigation(),reopened.locator('button[value=save]').click()]);
    assert(await reopened.locator('.record-actions').isVisible());
    const record = reopened.url();
    assert((await reopened.locator('main').innerText()).includes('Demo Hospital Visit'));
    assert(!(await reopened.locator('main').innerText()).includes('Draft'));
    result.workflow.push('Regular hospital visit saves without destination or progress selector');
    await reopened.goto(base + '/bundles');
    assert.equal(await reopened.locator('a[href*="' + new URL(resume).searchParams.get('unfinished') + '"]').count(),0);
    await second.close();
    // Failed autosave must be visible and must not silently navigate away.
    await page.goto(base + '/bundles/new');
    await page.route('**/visits/unfinished', route => route.fulfill({status:503,contentType:'application/json',body:'{}'}));
    await page.locator('[name=name]').fill('Failure Demo');
    await page.locator('[data-autosave-status][role=alert]').waitFor();
    await page.locator('.sidebar a[href^="/patients"]').click();
    assert.equal(new URL(page.url()).pathname,'/bundles/new');
    assert((await page.locator('[data-autosave-status]').innerText()).includes('Not saved'));
    await page.unroute('**/visits/unfinished');
    await Promise.all([page.waitForURL('**/bundles?*'),page.locator('button[value=save_later]').click()]);
    result.workflow.push('Save failure prevents navigation; explicit retry saves the unfinished record');
    for (const lang of ['en','ur','ps']) {
      for (const width of [320,393,768,1440]) {
        await page.setViewportSize({width,height:950});
        for (const url of ['/bundles/new', '/bundles', new URL(record).pathname]) {
          await page.goto(base + url + '?lang=' + lang);
          await page.evaluate(() => document.documentElement.style.fontSize='200%');
          assert(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth + 1), `${lang} ${width} ${url}: overflow`);
          assert(!(await page.locator('body').innerText()).includes('[Missing translation:'));
          await page.keyboard.press('Tab');
          assert(await page.evaluate(() => document.activeElement.tagName !== 'BODY'));
          result.largeText.push({lang,width,page:url});
          if (width===320 && url==='/bundles/new') await page.screenshot({path:path.join(output,lang+'-large-text-320.png'),fullPage:true});
        }
      }
    }
    assert.deepEqual(result.errors,[]); assert.deepEqual(result.externalRequests,[]);
    fs.writeFileSync(path.join(output,'visit-browser-results.json'),JSON.stringify(result,null,2));
    console.log(JSON.stringify({workflow:result.workflow,largeTextChecks:result.largeText.length,errors:result.errors}));
  } finally { await browser.close(); }
})().catch(error => {console.error(error);process.exit(1);});
