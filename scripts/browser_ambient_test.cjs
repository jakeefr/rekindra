const {chromium}=require(process.env.REKINDRA_PLAYWRIGHT_PATH||'playwright');
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
(async()=>{
 const out=path.resolve('.local/assembly-loop/ambient');fs.mkdirSync(out,{recursive:true});
 const browser=await chromium.launchPersistentContext(path.join(out,'profile'),{channel:'chrome',headless:true});
 try{
  const page=await browser.newPage();await page.setContent('<body></body>');await page.addScriptTag({path:path.resolve('runtime/world.js')});
  const result=await page.evaluate(()=>{
   const key={at:0,eye:[0,0,7],target:[0,0,0],fov:45};
   const scene={width:1280,height:720,camera:[key,{...key,at:12}],environment:{sky_top:'#777777',sky_bottom:'#777777',fog_color:'#000000',fog_density:0,light_color:'#FFFFFF',light_direction:[1,1,2],sun_size:.05,sun_strength:0,fill_strength:0},objects:[{id:'sphere',segments:[96,64],color:'#FFFFFF',color_high:'#FFFFFF',roughness:1,metalness:0,emission:0}]};
   const programs=[{position:['1.7*cos(u*2.*pi)*sin(v*pi)','1.7*cos(v*pi)','1.7*sin(u*2.*pi)*sin(v*pi)'],color_mix:'0.'}];
   function sample(extra){const s={...scene,environment:{...scene.environment,...extra}};const r=RekindraWorld.createRenderer(s,programs);const c=document.createElement('canvas');c.width=1280;c.height=720;const x=c.getContext('2d');x.drawImage(r.render(0),0,0);const pixels=x.getImageData(0,0,1280,720).data;const top=Array.from(x.getImageData(640,240,1,1).data),bottom=Array.from(x.getImageData(640,480,1,1).data),png=c.toDataURL().split(',')[1];r.dispose();return{pixels,top,bottom,png}}
   const baseline=sample({}),defaults=sample({ambient_strength:1,ground_strength:0,ground_color:'#FF0000'}),ground=sample({ground_strength:1,ground_color:'#FF0000'}),dark=sample({ambient_strength:0});
   let differences=0;for(let i=0;i<baseline.pixels.length;i++)differences+=baseline.pixels[i]!==defaults.pixels[i];
   return{differences,baseline:{top:baseline.top,bottom:baseline.bottom},ground:{top:ground.top,bottom:ground.bottom},dark:dark.bottom,images:{baseline:baseline.png,ground:ground.png,dark:dark.png}};
  });
  for(const [name,png] of Object.entries(result.images))fs.writeFileSync(path.join(out,name+'.png'),Buffer.from(png,'base64'));delete result.images;
  fs.writeFileSync(path.join(out,'result.json'),JSON.stringify(result,null,2));console.log(JSON.stringify(result));
  assert.equal(result.differences,0,'Explicit defaults changed legacy render');
  const tint=a=>a[0]-a[1];assert.ok(tint(result.ground.bottom)>tint(result.ground.top)+20,'Ground response not orientation dependent');
  assert.ok(result.dark[0]<result.baseline.bottom[0]-30,'Ambient intensity failed');
 }finally{await browser.close()}
})().catch(e=>{console.error(e);process.exitCode=1});
