// Read-only final enlarged-text checks on the isolated fictional server.
const {chromium}=require('playwright');
const assert=require('node:assert/strict');
const fs=require('node:fs');
(async()=>{
 const channel=process.env.SR_BROWSER_CHANNEL||'msedge';
 const browser=await chromium.launch({...(channel==='chromium'?{}:{channel}),headless:true});
 try {
  const page=await browser.newPage({viewport:{width:320,height:900}});
  const rows=[];fs.mkdirSync('tmp/final-layout',{recursive:true});
  for(const language of ['en','ur','ps']) {
   await page.goto('http://127.0.0.1:5091/attachments/AT-001/edit?lang='+language);
   const initial=await page.evaluate(()=>({root:parseFloat(getComputedStyle(document.documentElement).fontSize),body:parseFloat(getComputedStyle(document.body).fontSize)}));
   await page.evaluate(({root,body})=>{document.documentElement.style.fontSize=(root*2)+'px';document.body.style.fontSize=(body*2)+'px';},initial);
   const dimensions=await page.evaluate(()=>{
    const button=document.querySelector('.language-switch button');
    const broken=[];
    const walker=document.createTreeWalker(button,NodeFilter.SHOW_TEXT);let node;
    while((node=walker.nextNode())) for(const match of node.textContent.matchAll(/\S+/g)) {
     const range=document.createRange();range.setStart(node,match.index);range.setEnd(node,match.index+match[0].length);
     if(range.getClientRects().length>1) broken.push(match[0]);
    }
    return {viewport:innerWidth,scrollWidth:document.documentElement.scrollWidth,bodyFont:parseFloat(getComputedStyle(document.body).fontSize),buttonWidth:button.clientWidth,buttonHeight:button.clientHeight,brokenWords:broken};
   });
   assert.equal(dimensions.scrollWidth,320,language+' page reflow');
   assert.equal(dimensions.bodyFont,initial.body*2,language+' actual enlargement');
   assert.deepEqual(dimensions.brokenWords,[],language+' language action words');
   await page.screenshot({path:'tmp/final-layout/edit-320-large-'+language+'.png',fullPage:true});
   rows.push({language,...dimensions});
  }
  fs.writeFileSync('tmp/final-layout/results.json',JSON.stringify(rows,null,2));
  console.log('PASS: final320px/actual200% EN/UR/PS reflow and complete language-action words',JSON.stringify(rows));
 } finally {await browser.close();}
})().catch(error=>{console.error(error);process.exitCode=1;});
