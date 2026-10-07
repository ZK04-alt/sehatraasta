// EVIDENCE CLASS: AUTOMATED. Isolated fictional browser, axe + rendered checks.
const {chromium}=require('playwright');
const fs=require('node:fs');
const path=require('node:path');
const assert=require('node:assert/strict');
(async()=>{
 const browser=await chromium.launch({channel:process.env.SR_BROWSER_CHANNEL||'msedge',headless:true});
 const folder='tmp/final-accessibility';fs.mkdirSync(folder,{recursive:true});
 const axe=path.resolve('tmp/final-a11y/node_modules/axe-core/axe.min.js');
 const rows=[];
 try {
  // Test instrumentation only: axe injection needs bypassCSP. Product CSP is
  // separately checked with ordinary browser contexts and security tests.
  const page=await browser.newPage({viewport:{width:360,height:800},bypassCSP:true});
  const routes=['/patients','/patients/PK-001','/bundles/RB-001','/documents/new?patient_id=PK-001',
   '/attachments/AT-001/edit','/attachments/AT-001/replace','/attachments/AT-001/delete',
   '/removed','/patients/PK-001/print','/backups','/restore','/lookup','/privacy'];
  for(const language of ['en','ur','ps']) for(const route of routes){
   const response=await page.goto('http://127.0.0.1:5091'+route+(route.includes('?')?'&':'?')+'lang='+language);
   assert.equal(response.status(),200,route);
   await page.addScriptTag({path:axe});
   const result=await page.evaluate(async()=>{
    const scan=await axe.run(document,{runOnly:{type:'tag',values:['wcag2a','wcag2aa','wcag21a','wcag21aa','best-practice']}});
    return {version:axe.version,violations:scan.violations.map(v=>({id:v.id,impact:v.impact,nodes:v.nodes.map(n=>({target:n.target,summary:n.failureSummary}))})),
     incomplete:scan.incomplete.map(v=>({id:v.id,nodes:v.nodes.length})),passes:scan.passes.length,
     htmlLang:document.documentElement.lang,direction:document.documentElement.dir,overflow:document.documentElement.scrollWidth>innerWidth};
   });
   rows.push({language,route,...result});
  }
  await page.goto('http://127.0.0.1:5091/documents/new?patient_id=PK-001&lang=en');
  await page.keyboard.press('Tab');
  assert.equal(await page.locator(':focus').count(),1,'visible keyboard focus exists');
  fs.writeFileSync(folder+'/axe.json',JSON.stringify({evidence_class:'AUTOMATED',rows},null,2));
  const violations=rows.flatMap(r=>r.violations.map(v=>({language:r.language,route:r.route,...v})));
  console.log(JSON.stringify({evidence_class:'AUTOMATED',pages:rows.length,axe:rows[0].version,violations,overflow:rows.filter(r=>r.overflow),humanTalkBack:'MISSING HUMAN EVIDENCE'}));
  if(violations.length||rows.some(r=>r.overflow))process.exitCode=1;
 }finally{await browser.close();}
})().catch(e=>{console.error(e);process.exitCode=1;});
