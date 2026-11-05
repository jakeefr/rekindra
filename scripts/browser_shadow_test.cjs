// Development-only real-GPU regression. Uses installed Chrome; not a plugin dependency.
const assert=require('node:assert/strict'),fs=require('node:fs'),path=require('node:path');
const {chromium}=require(process.env.REKINDRA_PLAYWRIGHT_PATH||'playwright');
(async()=>{
 const out=path.resolve(process.env.REKINDRA_BROWSER_OUTPUT||'.local/shadow-regression');fs.mkdirSync(out,{recursive:true});
 const context=await chromium.launchPersistentContext(path.join(out,'profile'),{channel:'chrome',headless:true});
 try{
  const page=await context.newPage();await page.setContent('<body></body>');
  const source=fs.readFileSync(path.resolve(__dirname,'../runtime/world.js'),'utf8');
  assert.ok(source.includes('pixel=vec4(displayColor(lit),1.);'));
  await page.addScriptTag({content:source.replace('pixel=vec4(displayColor(lit),1.);','pixel=vec4(vec3(visibility(worldPos,nl)),1.);')});
  const result=await page.evaluate(()=>{
   const camera={at:0,eye:[0,8,12],target:[0,0,0],fov:45};
   const material={id:'receiver',segments:[8,8],color:'#FFFFFF',color_high:'#FFFFFF',roughness:.5,metalness:0,emission:0};
   const scene={width:1280,height:720,camera:[camera,{...camera,at:12}],environment:{sky_top:'#000000',sky_bottom:'#000000',fog_color:'#000000',fog_density:0,light_color:'#FFFFFF',light_direction:[1,.14,.4],sun_size:.15,sun_strength:1},objects:[material]};
   const programs=[{position:['(u-.5)*18.','0.','(v-.5)*18.'],color_mix:'0.'}];
   const sample=(renderer,points)=>{renderer.render(0);const copy=document.createElement('canvas');copy.width=1280;copy.height=720;const ctx=copy.getContext('2d');ctx.drawImage(renderer.canvas,0,0);return points.map(p=>{const [x,y]=RekindraWorld.projectPoint(p,camera,1280,720);return ctx.getImageData(Math.round(x),Math.round(y),1,1).data[0]})};
   const points=[];for(let x=-3;x<=3;x++)for(let z=-3;z<=3;z++)points.push([x,0,z]);
   let r=RekindraWorld.createRenderer(scene,programs);const clear=sample(r,points);r.dispose();
   // A real elevated occluder must still cast a shadow: this prevents "fixing" acne by disabling shadows.
   scene.objects.push({...material,id:'blocker'});programs.push({position:['(u-.5)*2.','1.','(v-.5)*2.'],color_mix:'0.'});
   r=RekindraWorld.createRenderer(scene,programs);const occluded=sample(r,[[-1/.14,0,-.4/.14]]);r.dispose();
   return {clear,occluded};
  });
  fs.writeFileSync(path.join(out,'result.json'),JSON.stringify(result,null,2));
  console.log(JSON.stringify({minClear:Math.min(...result.clear),occluded:result.occluded}));
  assert.ok(Math.min(...result.clear)>=245,'An isolated planar receiver shadows itself');
  assert.ok(result.occluded[0]<100,'The elevated blocker no longer casts its expected shadow');
 }finally{await context.close();}
})().catch(e=>{console.error(e);process.exitCode=1});
