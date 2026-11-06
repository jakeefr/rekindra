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
   const basic={open:sample([]),closed:sample(['v0','v1']),moved:sample(['v0','v1'],4)};
   program.color_detail='.3*sin(u*60.)';program.bump_detail='.05*cos(u*80.)';
   basic.detailed=sample(['v0','v1']);
   // Look under a floating vertical tube: only its lid should shadow the floor.
   scene.camera=scene.camera.map(k=>({...k,eye:[0,4,10]}));scene.environment.light_direction=[0,1,0];
   const tube=scene.objects[0];tube.segments=[32,8];
   scene.objects=[{...tube,id:'floor',caps:[],color:'#FFFFFF',color_high:'#FFFFFF'},tube];
   tube.instances=[{offset:[2,0,0],scale:[1,1,1]}];
   const programs=[{position:['(u-.5)*12.','0.','(v-.5)*12.'],color_mix:'0.'},{position:['cos(u*2.*pi)','1.5+v*1.5','sin(u*2.*pi)'],color_mix:'0.'}];
   function shadow(caps){tube.caps=caps;const r=RekindraWorld.createRenderer(scene,programs);const c=document.createElement('canvas');c.width=1280;c.height=720;const x=c.getContext('2d');x.drawImage(r.render(0),0,0);const [px,py]=RekindraWorld.projectPoint([2,0,0],scene.camera[0],1280,720);const value=x.getImageData(Math.round(px),Math.round(py),1,1).data[0];r.dispose();return value}
   return{...basic,shadow:{open:shadow([]),closed:shadow(['v1'])}};
  });
  for(const [name,s] of Object.entries(result)){if(s.png){fs.writeFileSync(path.join(out,name+'.png'),Buffer.from(s.png,'base64'));delete s.png}}
  fs.writeFileSync(path.join(out,'result.json'),JSON.stringify(result,null,2));console.log(JSON.stringify(result));
  assert.ok(result.open.center[2]>result.open.center[0],'Open tube must show blue sky');
  assert.ok(result.closed.center[0]>result.closed.center[2]+40,'Closed tube must cover its center with the lit cap');
  assert.deepEqual(result.moved.center,result.open.center,'Cap must follow animated body away from center');
  assert.deepEqual(result.detailed.center,result.closed.center,'Fine side detail must not distort cap shading');
  assert.ok(result.shadow.open>result.shadow.closed+40,'Cap failed to cast its own shadow');
 }finally{await browser.close()}
})().catch(e=>{console.error(e);process.exitCode=1});
