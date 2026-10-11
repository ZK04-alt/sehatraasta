// Export the existing logo. This does not create or change the chosen design.
const path=require('node:path');
const sharp=require('sharp');
const root=path.resolve(__dirname,'..');
(async()=>{
  for(const size of [192,512]){
    const mark=Math.floor(size*.75),edge=Math.floor((size-mark)/2);
    await sharp(path.join(root,'src/sehatraasta/web/static/favicon.svg'))
      .resize(mark,mark).flatten({background:'#F2EEE5'})
      .extend({top:edge,bottom:size-mark-edge,left:edge,right:size-mark-edge,background:'#F2EEE5'})
      .png().toFile(path.join(root,'browser',`icon-${size}.png`));
  }
})().catch(error=>{console.error(error.message);process.exitCode=1;});
