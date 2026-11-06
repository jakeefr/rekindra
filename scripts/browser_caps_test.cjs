const {chromium}=require(process.env.REKINDRA_PLAYWRIGHT_PATH||'playwright');
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
(async()=>{
 const out=path.resolve(process.env.REKINDRA_BROWSER_OUTPUT||'.local/caps-regression');fs.mkdirSync(out,{recursive:true});
 const browser=await chromium.launchPersistentContext(path.join(out,'profile'),{channel:'chrome',headless:true});
 try{
  const page=await browser.newPage();await page.setContent('<body></body>');await page.addScriptTag({path:path.resolve(__dirname,'../runtime/world.js')});
  const result=await page.evaluate(()=>{
   const key={at:0,eye:[0,0,6],target:[0,0,0],fov:45};
   const scene={width:1280,height:720,camera:[key,{...key,at:12}],environment:{sky_top:'#164583',sky_bottom:'#164583',fog_color:'#000000',fog_density:0,light_color:'#FFFFFF',light_direction:[1,1,2],sun_size:.05,sun_strength:1,fill_strength:.2},objects:[{id:'tube',segments:[32,4],color:'#EF7822',color_high:'#EF7822',roughness:.8,metalness:0,emission:0}]};
   const program={position:['cos(u*2.*pi)+t*.4','sin(u*2.*pi)','v*2.-1.'],color_mix:'0.'};
   function sample(caps,t=0){scene.objects[0].caps=caps;const r=RekindraWorld.createRenderer(scene,[program]);const c=document.createElement('canvas');c.width=1280;c.height=720;const x=c.getContext('2d');x.drawImage(r.render(t),0,0);const center=Array.from(x.getImageData(640,360,1,1).data),png=c.toDataURL().split(',')[1];r.dispose();return{center,png}}
   return{open:sample([]),closed:sample(['v0','v1']),moved:sample(['v0','v1'],4)};
  });
  for(const [name,s] of Object.entries(result)){fs.writeFileSync(path.join(out,name+'.png'),Buffer.from(s.png,'base64'));delete s.png}
  fs.writeFileSync(path.join(out,'result.json'),JSON.stringify(result,null,2));console.log(JSON.stringify(result));
  assert.ok(result.open.center[2]>result.open.center[0],'Open tube must show blue sky');
  assert.ok(result.closed.center[0]>result.closed.center[2]+40,'Closed tube must cover its center with the lit cap');
  assert.deepEqual(result.moved.center,result.open.center,'Cap must follow animated body away from center');
 }finally{await browser.close()}
})().catch(e=>{console.error(e);process.exitCode=1});
