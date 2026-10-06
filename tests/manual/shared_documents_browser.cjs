// Real document actions against the isolated fictional preview only.
const {chromium} = require('playwright');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const path = require('node:path');
(async () => {
  const base = process.env.SR_PREVIEW_URL || 'http://127.0.0.1:5067';
  const output = path.resolve('tmp/shared-interface-20261004/documents');
  fs.mkdirSync(output, {recursive:true});
  const browser = await chromium.launch({channel:'msedge',headless:true});
  try {
    const page = await browser.newPage({viewport:{width:1280,height:900}});
    const errors = [];
    page.on('pageerror', error => errors.push(error.message));
    await page.goto(base+'/bundles/SR-DEMO-001?lang=en');
    const [json] = await Promise.all([page.waitForEvent('download'),page.locator('form[action*="/export"] button').click()]);
    await json.saveAs(path.join(output,'referral.json'));
    const data = fs.readFileSync(path.join(output,'referral.json'),'utf8');
    const exported = JSON.parse(data);
    assert.equal(exported.bundle.cost_entries[0].amount_pkr, '2500');
    await page.locator('details.section').filter({has:page.locator('#passport-confirm')}).locator('summary').click();
    await page.locator('#passport-confirm').check();
    const [passport] = await Promise.all([page.waitForEvent('download'),page.locator('form[action*="/passport"] button').click()]);
    await passport.saveAs(path.join(output,'referral-passport.zip'));
    assert.equal(fs.readFileSync(path.join(output,'referral-passport.zip')).subarray(0,2).toString(),'PK');
    await page.goto(base+'/bundles/SR-DEMO-001/print?lang=en');
    await page.emulateMedia({media:'print'});
    assert.equal(await page.locator('.sidebar').isVisible(),false);
    assert.equal(await page.locator('.masthead').isVisible(),false);
    assert.equal(await page.locator('details.record-section').count(),0);
    assert.equal(await page.locator('section.record-section').count(),6);
    assert.equal(await page.locator('.qr').isVisible(),true);
    assert.ok((await page.locator('body').innerText()).includes('Fictional medicine A'));
    await page.pdf({path:path.join(output,'referral-print.pdf'),format:'A4',printBackground:true});
    await page.emulateMedia({media:'screen'});
    await page.goto(base+'/backups?lang=en');
    await page.locator('#confirm').check();
    const [backup] = await Promise.all([page.waitForEvent('download'),page.locator('button[value=save]').click()]);
    await backup.saveAs(path.join(output,'backup.zip'));
    assert.equal(fs.readFileSync(path.join(output,'backup.zip')).subarray(0,2).toString(),'PK');
    assert.deepEqual(errors,[]);
    console.log('JSON export, consented passport download, complete print/QR and backup download passed.');
  } finally { await browser.close(); }
})().catch(error=>{console.error(error);process.exitCode=1;});
