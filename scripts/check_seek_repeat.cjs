// Development-only real-browser regression. Supply a saved scene HTML.
// Separate evaluate calls are essential: a synchronous capture loop hid the defect.
const {chromium}=require(process.env.REKINDRA_PLAYWRIGHT_PATH||'playwright');
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
const {pathToFileURL}=require('node:url');
(async()=>{
  const out=path.resolve(process.argv[3]);fs.mkdirSync(out,{recursive:true});
  const browser=await chromium.launchPersistentContext(path.join(out,'profile'),{channel:'chrome',headless:true,viewport:{width:1400,height:1200}});
  const results=[];
  try{for(let run=0;run<10;run++){
    const page=await browser.newPage();await page.goto(pathToFileURL(path.resolve(process.argv[2])).href);await page.waitForFunction(()=>globalThis.rekindra?.ready);
    const a=await page.evaluate(()=>{rekindra.renderAt(1);const a=document.querySelector('#stage').toDataURL();rekindra.renderAt(2.5);document.querySelector('#stage').toDataURL();return a});
    const b=await page.evaluate(()=>{rekindra.renderAt(.1);rekindra.renderAt(1);return document.querySelector('#stage').toDataURL()});
    const result=await page.evaluate(async([a,b])=>{
      const pixels=async url=>{const i=new Image();i.src=url;await i.decode();const c=document.createElement('canvas');c.width=i.width;c.height=i.height;const x=c.getContext('2d');x.drawImage(i,0,0);return x.getImageData(0,0,c.width,c.height).data};
      const x=await pixels(a),y=await pixels(b);let changed=0,maxDelta=0;
      for(let i=0;i<x.length;i++){const d=Math.abs(x[i]-y[i]);if(d)changed++;maxDelta=Math.max(maxDelta,d)}return{changed,maxDelta};
    },[a,b]);results.push({run,...result});await page.close();
  }}finally{await browser.close()}
  fs.writeFileSync(path.join(out,'result.json'),JSON.stringify(results,null,2));console.log(JSON.stringify(results));
  assert.ok(results.every(r=>r.changed===0),'Repeated seeking changed rendered pixels');
})().catch(e=>{console.error(e);process.exitCode=1});
