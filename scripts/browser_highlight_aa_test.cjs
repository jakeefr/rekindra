// GPU quality regression against an independently higher-resolution reference.
const {chromium}=require(process.env.REKINDRA_PLAYWRIGHT_PATH||'playwright');
const fs=require('fs'),path=require('path'),assert=require('assert/strict');
(async()=>{
 const fixture=JSON.parse(fs.readFileSync(process.argv[2],'utf8')),out=path.resolve(process.argv[3]);fs.mkdirSync(out,{recursive:true});
 const browser=await chromium.launch({channel:'chrome',headless:true});const captures={};
 try{
  for(const variant of ['baseline','default','reference']){
   const page=await browser.newPage();await page.addScriptTag({path:path.resolve('runtime/world.js')});
   captures[variant]=await page.evaluate(({fixture,variant})=>{
    const scene=structuredClone(fixture.scene);if(variant==='reference'){scene.width*=4;scene.height*=4;}
    const r=RekindraWorld.createRenderer(scene,fixture.programs,variant==='default'?undefined:{sampleScale:1});
    const c=document.createElement('canvas');c.width=fixture.scene.width;c.height=fixture.scene.height;const x=c.getContext('2d');x.imageSmoothingQuality='high';
    const times=[4,6.5,10.8,14.8,16],frames=[],start=performance.now();
    for(const t of times){x.drawImage(r.render(t),0,0,c.width,c.height);frames.push({pixels:Array.from(x.getImageData(0,0,c.width,c.height).data),png:c.toDataURL().split(',')[1]});}
    x.drawImage(r.render(4),0,0,c.width,c.height);const repeat=Array.from(x.getImageData(0,0,c.width,c.height).data).every((v,i)=>v===frames[0].pixels[i]);
    const dimensions=[r.canvas.width,r.canvas.height];r.dispose();return {frames,repeat,dimensions,elapsed:performance.now()-start};
   },{fixture,variant});await page.close();
  }
  const metrics=[];for(let k=0;k<5;k++){
   const a=captures.baseline.frames[k].pixels,b=captures.default.frames[k].pixels,r=captures.reference.frames[k].pixels;let ae=0,be=0,n=0;
   for(let i=0;i<a.length;i+=4){if(Math.max(a[i],a[i+1],a[i+2],r[i],r[i+1],r[i+2])<140)continue;for(let j=0;j<3;j++){ae+=Math.abs(a[i+j]-r[i+j]);be+=Math.abs(b[i+j]-r[i+j]);n++;}}
   metrics.push({baseline:ae/n,filtered:be/n,ratio:be/ae});
   for(const variant of Object.keys(captures))fs.writeFileSync(path.join(out,variant+'-'+k+'.png'),Buffer.from(captures[variant].frames[k].png,'base64'));
  }
  fs.writeFileSync(path.join(out,'result.json'),JSON.stringify({metrics,repeat:Object.fromEntries(Object.entries(captures).map(([k,v])=>[k,v.repeat])),elapsed:Object.fromEntries(Object.entries(captures).map(([k,v])=>[k,v.elapsed]))},null,2));
  for(const v of Object.values(captures))assert.equal(v.repeat,true,'Same-time pixel repeat must remain exact');
  assert.deepEqual(captures.default.dimensions,[fixture.scene.width,fixture.scene.height],'Public canvas dimensions unchanged');
  for(const m of metrics){assert.ok(m.baseline>1,'Fixture must expose aliasing');assert.ok(m.ratio<.6,`Expected >=40% highlight error reduction, ratio=${m.ratio}`);}
  console.log(JSON.stringify(metrics));
 }finally{await browser.close()}
})().catch(e=>{console.error(e);process.exitCode=1});
