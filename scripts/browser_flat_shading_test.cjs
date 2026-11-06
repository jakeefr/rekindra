const {chromium}=require(process.env.REKINDRA_PLAYWRIGHT_PATH||'playwright');
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
(async()=>{
 const out=path.resolve(process.env.REKINDRA_BROWSER_OUTPUT||'.local/flat-shading');fs.mkdirSync(out,{recursive:true});
 const browser=await chromium.launchPersistentContext(path.join(out,'profile'),{channel:'chrome',headless:true});
 try{
  const page=await browser.newPage();await page.setContent('');await page.addScriptTag({path:path.resolve('runtime/world.js')});
  const result=await page.evaluate(()=>{
   const camera={at:0,eye:[0,0,6],target:[0,0,0],fov:45};
   const object={id:'octagon',segments:[8,4],color:'#BBBBBB',color_high:'#BBBBBB',roughness:1,metalness:0,emission:.1,caps:['v0','v1']};
   const scene={width:1280,height:720,camera:[camera,{...camera,at:12}],environment:{sky_top:'#000000',sky_bottom:'#000000',fog_color:'#000000',fog_density:0,light_color:'#FFFFFF',light_direction:[1,0,1],sun_size:.05,sun_strength:1,fill_strength:0,ambient_strength:0},objects:[object]};
   const program={position:['cos(u*2.*pi)','(v-.5)*3.','sin(u*2.*pi)'],color_mix:'0.'};
   function capture(shading){if(shading)object.shading=shading;else delete object.shading;
    const r=RekindraWorld.createRenderer(scene,[program]),c=document.createElement('canvas');c.width=1280;c.height=720;
    const x=c.getContext('2d');x.drawImage(r.render(0),0,0);r.dispose();
    const samples=[-.15,-.55].map(px=>{const pz=1+px*(1-Math.SQRT1_2)/Math.SQRT1_2;const [sx,sy]=RekindraWorld.projectPoint([px,0,pz],camera,1280,720);return Array.from(x.getImageData(Math.round(sx),Math.round(sy),1,1).data)});
    const pixels=x.getImageData(0,0,1280,720).data,mask=[];for(let i=0;i<pixels.length;i+=4)mask.push(pixels[i]+pixels[i+1]+pixels[i+2]>0?1:0);
    return{samples,mask,png:c.toDataURL().split(',')[1]};
   }return{legacy:capture(),smooth:capture('smooth'),flat:capture('flat')};
  });
  assert.equal(result.legacy.png,result.smooth.png,'Default must retain exact smooth path');
  const changedCoverage=result.flat.mask.reduce((n,v,i)=>n+(v!==result.smooth.mask[i]),0);
  assert.equal(changedCoverage,0,'Shading must not change geometry coverage');
  const delta=x=>Math.abs(x.samples[0][0]-x.samples[1][0]);
  const metrics={smooth:result.smooth.samples,flat:result.flat.samples,smoothDelta:delta(result.smooth),flatDelta:delta(result.flat)};
  for(const [name,r] of Object.entries(result))fs.writeFileSync(path.join(out,name+'.png'),Buffer.from(r.png,'base64'));
  fs.writeFileSync(path.join(out,'result.json'),JSON.stringify(metrics,null,2));console.log(metrics);
  assert.ok(metrics.smoothDelta>=8,'Smooth normals should visibly curve across the face');
  assert.ok(metrics.flatDelta<=3,'One planar face should retain constant directional shading');
 }finally{await browser.close()}
})().catch(e=>{console.error(e);process.exitCode=1});
