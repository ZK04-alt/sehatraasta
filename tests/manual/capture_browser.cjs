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
    const image = await page.evaluate(()=>{const canvas=document.createElement('canvas');canvas.width=canvas.height=1;
      const context=canvas.getContext('2d');context.fillStyle='rgb(12,34,56)';context.fillRect(0,0,1,1);return canvas.toDataURL().split(',')[1];});
    await page.locator('#file').setInputFiles({name:'fictional-minimal.png', mimeType:'image/png',buffer:Buffer.from(image,'base64')});
    await page.locator('button[value=save]').click();
    await page.waitForURL('**/bundles/**');
    assert.ok((await page.locator('main').innerText()).includes('Date not known'));
    assert.ok((await page.locator('main').innerText()).includes('fictional-minimal.png'));
    assert.ok((await page.locator('main').innerText()).includes('Fictional interrupted capture'));
    assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth <= innerWidth), true);
    await page.screenshot({path:'tmp/resumed-browser/saved-paper-360.png',fullPage:true});
    await page.goto(base+'/documents/new?lang=en');
    await page.locator('#mode').selectOption('new');
    await page.locator('#name').fill('Fictional discard target');
    await page.waitForFunction(()=>document.querySelector('[name=unfinished_id]').value);
    await page.locator('#file').setInputFiles({name:'unsupported.txt',mimeType:'text/plain',buffer:Buffer.from('Fictional unsupported paper')});
    await page.locator('button[value=save]').click();
    await page.waitForSelector('[role=alert]');
    assert.ok((await page.locator('[role=alert]').innerText()).includes('PDF, PNG or JPEG'));
    assert.equal(await page.locator('#name').inputValue(),'Fictional discard target');
    await page.goto(base+'/?lang=en');
    assert.ok((await page.locator('main').innerText()).includes('fictional-minimal.png'));
    const draft=page.locator('article').filter({has:page.getByRole('heading',{name:'Fictional discard target',exact:true})});
    await draft.getByRole('link',{name:'Discard draft',exact:true}).click();
    assert.ok((await page.locator('main').innerText()).includes('Fictional discard target'));
    await page.locator('[name=confirm]').check();await page.locator('.form-actions button').click();
    await page.waitForURL(url=>['/','/bundles'].includes(url.pathname));
    assert.equal(await page.getByRole('heading',{name:'Fictional discard target',exact:true}).count(),0);
    assert.ok((await page.locator('main').innerText()).includes('fictional-minimal.png'));
    console.log('PASS: shared initialization, patient context, interrupted text recovery, unknown-date paper-only save, specific file errors, visible retrieval cue and confirmed scoped draft discard');
  } finally { await browser.close(); }
})().catch(error => { console.error(error); process.exitCode=1; });
