// Diagnostic only: distinguish WebGL pixel changes from 2D canvas transfer changes.
const {chromium}=require(process.env.REKINDRA_PLAYWRIGHT_PATH||'playwright');
const fs=require('node:fs'),path=require('node:path'),{pathToFileURL}=require('node:url');
(async()=>{const out=path.resolve(process.argv[3]);fs.mkdirSync(out,{recursive:true});const browser=await chromium.launchPersistentContext(path.join(out,'profile'),{channel:'chrome',headless:true});const result=[];
try{for(let n=0;n<10;n++){
const page=await browser.newPage();await page.goto(pathToFileURL(path.resolve(process.argv[2])).href);await page.waitForFunction(()=>globalThis.rekindra?.ready);
await page.evaluate(()=>{
window.r=RekindraWorld.createRenderer(rekindra.scene,rekindra.data.programs);window.c=document.createElement('canvas');c.width=1280;c.height=720;window.x=c.getContext('2d');
window.capture=t=>{r.render(t);const gl=r.canvas.getContext('webgl2'),raw=new Uint8Array(1280*720*4);gl.readPixels(0,0,1280,720,gl.RGBA,gl.UNSIGNED_BYTE,raw);x.drawImage(r.canvas,0,0);return{raw,copy:x.getImageData(0,0,1280,720).data}};
window.a=capture(1);capture(2.5);
});
result.push(await page.evaluate(()=>{capture(.1);const b=capture(1),result={};for(const key of ['raw','copy']){let changed=0,max=0;const samples=[];for(let i=0;i<a[key].length;i++){const d=Math.abs(a[key][i]-b[key][i]);if(d){changed++;if(samples.length<6)samples.push([Math.floor(i/4)%1280,Math.floor(i/5120),i%4,a[key][i],b[key][i]])}max=Math.max(max,d)}result[key]={changed,max,samples}}r.dispose();return result}));await page.close();
}}finally{await browser.close()}fs.writeFileSync(path.join(out,'result.json'),JSON.stringify(result,null,2));console.log(JSON.stringify(result));})().catch(e=>{console.error(e);process.exitCode=1});
