// Fast internal review of a built scene; no claim of encoded-video verification.
const {chromium}=require(process.env.REKINDRA_PLAYWRIGHT_PATH||'playwright');
const fs=require('node:fs'),path=require('node:path'),{pathToFileURL}=require('node:url');
(async()=>{
 const out=path.resolve(process.argv[3]);fs.mkdirSync(out,{recursive:true});
 const browser=await chromium.launchPersistentContext(path.join(out,'profile'),{channel:'chrome',headless:true});
 try{
  const page=await browser.newPage();await page.goto(pathToFileURL(path.resolve(process.argv[2])).href);
  await page.waitForFunction(()=>globalThis.rekindra?.ready);
  const png=await page.evaluate(()=>{
   const c=document.createElement('canvas');c.width=1920;c.height=720;const x=c.getContext('2d');
   [1,3,5,7,9,11].forEach((t,i)=>{rekindra.renderAt(t);x.drawImage(document.querySelector('#stage'),i%3*640,Math.floor(i/3)*360,640,360)});
   return c.toDataURL().split(',')[1];
  });
  fs.writeFileSync(path.join(out,'preview.png'),Buffer.from(png,'base64'));
  for(const t of [1,7,11]){
   const png=await page.evaluate(t=>{rekindra.renderAt(t);return document.querySelector('#stage').toDataURL().split(',')[1]},t);
   fs.writeFileSync(path.join(out,`frame-${t}.png`),Buffer.from(png,'base64'));
  }
 }finally{await browser.close()}
})().catch(e=>{console.error(e);process.exitCode=1});
