// Shared website/Android UI checks against a separate, fictional preview.
const {chromium} = require('playwright');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');

(async () => {
  const base = process.env.SR_PREVIEW_URL || 'http://127.0.0.1:5067';
  const output = path.resolve(process.env.SR_PREVIEW_OUTPUT || 'tmp/shared-interface-20261004/browser');
  fs.mkdirSync(output, {recursive:true});
  const browser = await chromium.launch({channel:'msedge', headless:true});
  const results = [];
  try {
    for (const width of [320, 393, 600, 768, 900, 1280, 1440]) {
      for (const language of ['en','ur','ps']) {
        const context = await browser.newContext({viewport:{width,height:852},isMobile:true,hasTouch:true});
        const page = await context.newPage();
        const errors = [];
        const requests = [];
        page.on('pageerror', e => errors.push(e.message));
        page.on('request', r => requests.push(r.url()));
        for (const url of ['/bundles','/bundles/new','/bundles/SR-DEMO-001','/lookup','/patients']) {
          const response = await page.goto(base + url + '?lang=' + language);
          assert.equal(response.status(),200);
          await page.evaluate(() => document.fonts.ready);
          assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth),true,url);
          assert.equal(await page.locator('html').getAttribute('dir'),language==='en'?'ltr':'rtl');
          assert.equal(await page.locator('.sidebar a').count(),3);
          assert.equal((await page.locator('body').innerText()).includes('[Missing'),false);
          assert.equal(await page.locator('.brand img').evaluate(e=>e.complete && e.naturalWidth>0),true);
          assert.equal(await page.locator('body').evaluate(e=>getComputedStyle(e).backgroundColor),'rgb(242, 238, 229)');
          if (url==='/bundles') {
            assert.ok(await page.locator('.referral-card').count() >= 3);
            assert.ok((await page.locator('main').innerText()).includes('Amina Demo'));
            await page.locator('.app-menu > summary').tap();
            await page.locator('.app-menu a[href*="/backups"]').tap();
            await page.waitForURL('**/backups?lang='+language);
            assert.equal(new URL(page.url()).pathname,'/backups');
            await page.goto(base+url+'?lang='+language);
          }
          if (url==='/bundles/new') {
            assert.equal(await page.locator('[data-record-section][open]').count(),0);
            for (const element of await page.locator('input:not([type=hidden]):not([type=checkbox]), select, button:not([hidden])').all()) {
              if (await element.isVisible()) assert.ok((await element.boundingBox()).height>=51,await element.getAttribute('name'));
            }
            await page.locator('[data-repeat="medications"] > details > summary').tap();
            assert.equal(await page.locator('[data-repeat="medications"] > details').getAttribute('open'),'');
          }
          if (url==='/bundles/SR-DEMO-001') {
            assert.ok((await page.locator('.cost-total').innerText()).includes('2,500.00'));
            assert.equal(await page.locator('details.record-section').count(),6);
            assert.equal(await page.locator('details.record-section[open]').count(),0);
            await page.locator('details.record-section').filter({hasText:'Fictional medicine A'}).locator('summary').first().tap();
            assert.ok((await page.locator('body').innerText()).includes('Fictional medicine A'));
          }
          if (width===393 || width===1280) await page.screenshot({path:path.join(output,width+'-'+language+'-'+url.replaceAll('/','-')+'.png'),fullPage:true});
          results.push({width,language,url,passed:true});
        }
        await page.goto(base+'/bundles/new?lang='+language);
        await page.keyboard.press('Tab');
        assert.equal(await page.locator('body').evaluate(e=>e.classList.contains('keyboard-navigation')),true);
        assert.equal(await page.locator(':focus').evaluate(e=>getComputedStyle(e).outlineColor),'rgb(150, 98, 68)');
        await page.locator('.app-menu > summary').tap();
        assert.equal(await page.locator('body').evaluate(e=>e.classList.contains('keyboard-navigation')),false);
        await page.keyboard.press('Escape');
        assert.equal(await page.locator('.app-menu').getAttribute('open'),null);
        assert.deepEqual(errors,[]);
        assert.ok(requests.every(url=>url.startsWith(base)), 'Unexpected external asset request');
        await context.close();
      }
    }
    fs.writeFileSync(path.join(output,'results.json'),JSON.stringify(results,null,2));
    console.log(results.length+' responsive page checks passed; keyboard focus, touch feedback and offline assets checked.');
  } finally { await browser.close(); }
})().catch(e=>{console.error(e);process.exit(1)});
