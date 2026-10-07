// Run against the isolated fictional server, never a normal instance.
const {chromium} = require('playwright');
const assert = require('node:assert/strict');
const fs = require('node:fs');

(async () => {
  const base = process.argv[2] || 'http://127.0.0.1:5091';
  const channel = process.env.SR_BROWSER_CHANNEL || 'msedge';
  const browser = await chromium.launch({...(channel === 'chromium' ? {} : {channel}), headless:true});
  const page = await browser.newPage({viewport:{width:360,height:800}});
  const errors = [];
  page.on('pageerror', error => errors.push(error.message));
  try {
    await page.goto(base + '/documents/new?patient_id=PK-001&lang=en');
    await page.waitForLoadState('networkidle');
    assert.deepEqual(errors, [], 'Paper capture must initialize shared scripts without exceptions');
    assert.equal(await page.locator('#patient_id').inputValue(), 'PK-001');
    await page.locator('#mode').selectOption('new');
    await page.locator('#name').fill('Fictional interrupted capture');
    await page.waitForFunction(() => document.querySelector('[name=unfinished_id]').value);
    await page.reload();
    await page.waitForLoadState('networkidle');
    assert.equal(await page.locator('#name').inputValue(), 'Fictional interrupted capture');
    assert.deepEqual(errors, []);
    fs.mkdirSync('tmp/resumed-browser', {recursive:true});
    await page.screenshot({path:'tmp/resumed-browser/capture-360.png', fullPage:true});
    await page.locator('#file').setInputFiles({name:'fictional-minimal.png', mimeType:'image/png',
      buffer:Buffer.from('iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+aD1kAAAAASUVORK5CYII=', 'base64')});
    await page.locator('button[value=save]').click();
    await page.waitForURL('**/bundles/**');
    assert.ok((await page.locator('main').innerText()).includes('Date not known'));
    assert.ok((await page.locator('main').innerText()).includes('fictional-minimal.png'));
    assert.ok((await page.locator('main').innerText()).includes('Fictional interrupted capture'));
    assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth <= innerWidth), true);
    await page.screenshot({path:'tmp/resumed-browser/saved-paper-360.png',fullPage:true});
    console.log('PASS: shared initialization, patient context, interrupted text recovery and unknown-date paper-only save');
  } finally { await browser.close(); }
})().catch(error => { console.error(error); process.exitCode=1; });
