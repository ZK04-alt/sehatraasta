// Optional browser verification. Requires Playwright and a running local lab.
// NODE_PATH may point to an installed Playwright runtime.
const { chromium } = require('playwright');
const fs = require('fs');
const path = require('path');
const assert = require('assert');

(async () => {
  const browser = await chromium.launch({channel:'msedge',headless:true});
  const output = path.resolve('tmp/phase06-browser');
  fs.mkdirSync(output,{recursive:true});
  const states = ['initial','empty_submission','one_invalid','multiple_invalid','success','duplicate','empty_list','unavailable','404','500','print'];
  const result = {states:0, widths:[], keyboard:[], zoom:'CSS 200% reflow simulation; native browser zoom still needs manual review'};
  try {
    const context = await browser.newContext();
    await context.route('**/*', route => route.request().url().startsWith('http://127.0.0.1:8766/') ? route.continue() : route.abort());
    const page = await context.newPage();
    for (const language of ['en','ur','ps']) {
      for (const state of states) {
        await page.setViewportSize({width:320,height:900});
        await page.goto(`http://127.0.0.1:8766/states?lang=${language}&state=${state}`);
        assert.equal(await page.locator('html').getAttribute('dir'),language==='en'?'ltr':'rtl');
        assert(await page.evaluate(()=>document.documentElement.scrollWidth<=document.documentElement.clientWidth+1));
        const badLinks = await page.evaluate(()=>[...document.querySelectorAll('.summary a')].filter(a=>!document.getElementById(a.hash.slice(1))).length);
        assert.equal(badLinks,0);
        result.states++;
      }
      await page.goto(`http://127.0.0.1:8766/states?lang=${language}&state=multiple_invalid`);
      await page.locator('.summary').focus();
      await page.keyboard.press('Tab');
      assert.equal(await page.evaluate(()=>document.activeElement.getAttribute('href')),'#name');
      await page.keyboard.press('Enter');
      assert.equal(await page.evaluate(()=>document.activeElement.id),'name');
      await page.screenshot({path:path.join(output,`${language}-errors-320.png`),fullPage:true});
      await page.setViewportSize({width:640,height:1000});
      await page.evaluate(()=>document.documentElement.style.zoom='2');
      assert(await page.evaluate(()=>document.documentElement.scrollWidth<=document.documentElement.clientWidth+1));
      result.widths.push(language+': 320 CSS pixels and 200% CSS zoom');
      await page.evaluate(()=>document.querySelector('link[rel=stylesheet]').remove());
      assert.equal(await page.locator('html').getAttribute('dir'),language==='en'?'ltr':'rtl');
      const semantic = await page.evaluate(()=>[...document.querySelectorAll('label')].every(label=>document.getElementById(label.htmlFor)));
      assert(semantic);
      // A complete keyboard-only form submission in each language.
      await page.goto(`http://127.0.0.1:8766/?lang=${language}`);
      for (let i=0;i<20 && await page.evaluate(()=>document.activeElement.id)!=='name';i++) await page.keyboard.press('Tab');
      assert.equal(await page.evaluate(()=>document.activeElement.id),'name');
      assert.equal(await page.locator('#name').evaluate(el=>getComputedStyle(el).outlineWidth),'3px');
      const name='Demo مثال '+language+' '+Date.now();
      await page.keyboard.type(name);
      await page.keyboard.press('Tab');
      assert.equal(await page.evaluate(()=>document.activeElement.id),'date');
      await page.keyboard.type('2026-09-20');
      await page.keyboard.press('Tab');
      await page.keyboard.press('Space');
      await page.keyboard.press('Tab');
      await Promise.all([page.waitForURL('**/requests?**'),page.keyboard.press('Enter')]);
      assert(await page.locator('[role=status]').count());
      assert((await page.locator('main').innerText()).includes(name));
      result.keyboard.push(language+': saved by keyboard with visible focus');
    }
    await page.goto('http://127.0.0.1:8766/?lang=en');
    await page.locator('#name').fill('Original متن AP-123');
    await page.locator('#date').fill('2026-09-20');
    await page.locator('#language').selectOption('ps');
    await Promise.all([page.waitForNavigation(),page.locator('button[value=language]').click()]);
    assert.equal(await page.locator('#name').inputValue(),'Original متن AP-123');
    assert.equal(await page.locator('html').getAttribute('dir'),'rtl');
    await page.goto('http://127.0.0.1:8766/print?lang=ps');
    await page.emulateMedia({media:'print'});
    assert.equal(await page.locator('header').evaluate(el=>getComputedStyle(el).display),'none');
    await page.screenshot({path:path.join(output,'ps-print.png'),fullPage:true});
    fs.writeFileSync(path.join(output,'results.json'),JSON.stringify(result,null,2));
    console.log(JSON.stringify(result));
  } finally { await browser.close(); }
})();
