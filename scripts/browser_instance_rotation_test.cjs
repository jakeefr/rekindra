const {chromium}=require(process.env.REKINDRA_PLAYWRIGHT_PATH||'playwright');
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
(async()=>{
 const out=path.resolve('.local/inspection-loop/rotation');fs.mkdirSync(out,{recursive:true});
 const browser=await chromium.launchPersistentContext(path.join(out,'profile'),{channel:'chrome',headless:true});
 try{
  const page=await browser.newPage();await page.setContent('<body></body>');await page.addScriptTag({path:path.resolve('runtime/world.js')});
  const result=await page.evaluate(()=>{
   const key={at:0,eye:[0,0,8],target:[0,0,0],fov:45};
   const obj={id:'parts',segments:[32,8],caps:['v0','v1'],color:'#EF7822',color_high:'#EF7822',roughness:.8,metalness:0,emission:0,
    instances:[{offset:[-1.7,0,0],scale:[1.1,.3,.4]},{offset:[1.7,0,0],scale:[1.1,.3,.4],rotation:[0,0,Math.PI/2]}]};
   const scene={width:1280,height:720,camera:[key,{...key,at:12}],environment:{sky_top:'#164583',sky_bottom:'#164583',fog_color:'#000000',fog_density:0,light_color:'#FFFFFF',light_direction:[1,1,2],sun_size:.05,sun_strength:1,fill_strength:.2},objects:[obj]};
   const programs=[{position:['cos(u*2.*pi)','sin(u*2.*pi)','v*2.-1.'],color_mix:'0.'}];
   const r=RekindraWorld.createRenderer(scene,programs),c=document.createElement('canvas');c.width=1280;c.height=720;const x=c.getContext('2d');x.drawImage(r.render(0),0,0);r.dispose();
   const pix=x.getImageData(0,0,1280,720).data,boxes=[[1280,720,0,0],[1280,720,0,0]];
   for(let y=0;y<720;y++)for(let px=0;px<1280;px++){const i=(y*1280+px)*4;if(pix[i]>pix[i+2]+40){const b=boxes[px<640?0:1];b[0]=Math.min(b[0],px);b[1]=Math.min(b[1],y);b[2]=Math.max(b[2],px);b[3]=Math.max(b[3],y)}}
   const png=c.toDataURL().split(',')[1];
   scene.camera=scene.camera.map(k=>({...k,eye:[0,4,10]}));scene.environment.light_direction=[-1,1,0];
   obj.instances=[{offset:[0,0,0],scale:[1,1,1],rotation:[0,0,Math.PI/4]}];
   scene.objects=[{...obj,id:'floor',caps:[],instances:undefined,color:'#FFFFFF',color_high:'#FFFFFF'},obj];
   const ps=[{position:['(u-.5)*12.','0.','(v-.5)*12.'],color_mix:'0.'},{position:['cos(u*2.*pi)','1.5+v*1.5','sin(u*2.*pi)'],color_mix:'0.'}];
   function sample(caps){obj.caps=caps;const r=RekindraWorld.createRenderer(scene,ps);x.drawImage(r.render(0),0,0);const [px,py]=RekindraWorld.projectPoint([0,0,0],scene.camera[0],1280,720);const v=x.getImageData(Math.round(px),Math.round(py),1,1).data[0];r.dispose();return v}
   return{boxes,png,shadow:{open:sample([]),closed:sample(['v1'])}};
  });
  fs.writeFileSync(path.join(out,'rotation.png'),Buffer.from(result.png,'base64'));delete result.png;
  fs.writeFileSync(path.join(out,'result.json'),JSON.stringify(result,null,2));console.log(JSON.stringify(result));
  const [a,b]=result.boxes;assert.ok(a[2]-a[0]>2*(a[3]-a[1]));assert.ok(b[3]-b[1]>2*(b[2]-b[0]),'Rotation must follow nonuniform scale, before offset');
  assert.ok(result.shadow.open>result.shadow.closed+40,'Rotated cap must cast its expected shadow');
 }finally{await browser.close()}
})().catch(e=>{console.error(e);process.exitCode=1});
