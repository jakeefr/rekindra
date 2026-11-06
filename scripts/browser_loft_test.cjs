const {chromium}=require(process.env.REKINDRA_PLAYWRIGHT_PATH||'playwright');
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
(async()=>{
 const fixture=JSON.parse(fs.readFileSync(process.argv[2],'utf8')),out=path.resolve(process.argv[3]);fs.mkdirSync(out,{recursive:true});
 const browser=await chromium.launchPersistentContext(path.join(out,'profile'),{channel:'chrome',headless:true});
 try{
  const page=await browser.newPage();await page.setContent('');await page.addScriptTag({path:path.resolve('runtime/world.js')});
  const result=await page.evaluate(f=>{
   const scene=f.scene,programs=f.programs;
   function capture(){const r=RekindraWorld.createRenderer(scene,programs),c=document.createElement('canvas');c.width=1280;c.height=720;const x=c.getContext('2d');x.drawImage(r.render(0),0,0);r.dispose();return{c,x}}
   let {c,x}=capture();const pixels=x.getImageData(0,0,1280,720).data;
   const widths=[.3,1.5,2.7].map(y=>{const row=Math.round(RekindraWorld.projectPoint([0,y,0],scene.camera[0],1280,720)[1]);let min=1280,max=-1;for(let col=0;col<1280;col++){const i=(row*1280+col)*4;if(pixels[i]>10){min=Math.min(min,col);max=col}}return max-min+1});
   const png=c.toDataURL().split(',')[1];scene.camera=scene.camera.map(k=>({...k,eye:[0,8,0],target:[0,1.5,0]}));
   scene.objects[0].caps=[];const open=Array.from(capture().x.getImageData(640,360,1,1).data);
   scene.objects[0].caps=['v1'];const closed=Array.from(capture().x.getImageData(640,360,1,1).data);
   // Independent placement moves the entire closed loft away from the center ray.
   scene.objects[0].instances=[{offset:[3,0,0],scale:[1,1,1],rotation:[0,.4,0]}];
   const moved=Array.from(capture().x.getImageData(640,360,1,1).data);
   return{widths,png,open,closed,moved};
  },fixture);
  fs.writeFileSync(path.join(out,'loft.png'),Buffer.from(result.png,'base64'));delete result.png;
  fs.writeFileSync(path.join(out,'result.json'),JSON.stringify(result,null,2));console.log(result);
  assert.ok(result.widths[0]>result.widths[1]*2.5&&result.widths[2]>result.widths[1]*1.7,'Loft must follow the three distinct section profiles');
  assert.equal(result.open[0],0,'Open loft center must show background');
  assert.ok(result.closed[0]>40,'Loft cap must cover the opening');
  assert.equal(result.moved[0],0,'Cap must follow instance placement away from center');
 }finally{await browser.close()}
})().catch(e=>{console.error(e);process.exitCode=1});
