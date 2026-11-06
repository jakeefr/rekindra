const {chromium}=require(process.env.REKINDRA_PLAYWRIGHT_PATH||'playwright');
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
(async()=>{
 const out=path.resolve(process.env.REKINDRA_BROWSER_OUTPUT||'.local/instances-regression');fs.mkdirSync(out,{recursive:true});
 const browser=await chromium.launchPersistentContext(path.join(out,'profile'),{channel:'chrome',headless:true});
 try{
  const page=await browser.newPage();await page.setContent('<body></body>');await page.addScriptTag({path:path.resolve(__dirname,'../runtime/world.js')});
  const r=await page.evaluate(()=>{
   const key={at:0,eye:[0,0,8],target:[0,0,0],fov:45};
   const scene={width:1280,height:720,camera:[key,{...key,at:12}],environment:{sky_top:'#164583',sky_bottom:'#164583',fog_color:'#000000',fog_density:0,light_color:'#FFFFFF',light_direction:[1,1,2],sun_size:.05,sun_strength:1,fill_strength:.2},objects:[{id:'parts',segments:[32,4],caps:['v0','v1'],instances:[{offset:[-1.6,0,0],scale:[.5,.5,.5]},{offset:[1.6,0,0],scale:[.8,1,.5]}],color:'#EF7822',color_high:'#EF7822',roughness:.8,metalness:0,emission:0}]};
   const programs=[{position:['cos(u*2.*pi)','sin(u*2.*pi)','v*2.-1.'],color_mix:'0.'}];
   const renderer=RekindraWorld.createRenderer(scene,programs),c=document.createElement('canvas');c.width=1280;c.height=720;const x=c.getContext('2d');x.drawImage(renderer.render(0),0,0);
   const pixels=x.getImageData(0,0,1280,720).data;let left=0,right=0;
   for(let y=0;y<720;y++)for(let px=0;px<1280;px++){const i=(y*1280+px)*4;if(pixels[i]>pixels[i+2]+40){if(px<640)left++;else right++}}
   const center=Array.from(x.getImageData(640,360,1,1).data),png=c.toDataURL().split(',')[1];renderer.dispose();return{left,right,center,png};
  });
  fs.writeFileSync(path.join(out,'instances.png'),Buffer.from(r.png,'base64'));delete r.png;
  fs.writeFileSync(path.join(out,'result.json'),JSON.stringify(r,null,2));console.log(JSON.stringify(r));
  assert.ok(r.center[2]>r.center[0],'Untransformed object remained at origin');
  assert.ok(r.left>3000&&r.right>r.left*2,'Instances failed to appear with distinct nonuniform scales');
 }finally{await browser.close()}
})().catch(e=>{console.error(e);process.exitCode=1});
