// Real-browser material regression: fine color detail must not depend on mesh density.
const {chromium}=require(process.env.REKINDRA_PLAYWRIGHT_PATH||'playwright');
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
(async()=>{
 const out=path.resolve(process.env.REKINDRA_BROWSER_OUTPUT||'.local/material-regression');fs.mkdirSync(out,{recursive:true});
 const browser=await chromium.launchPersistentContext(path.join(out,'profile'),{channel:'chrome',headless:true});
 try{
  const page=await browser.newPage();await page.setContent('<body></body>');
  await page.addScriptTag({path:path.resolve(__dirname,'../runtime/world.js')});
  const result=await page.evaluate(()=>{
   const camera={at:0,eye:[0,0,6],target:[0,0,0],fov:45};
   const object={id:'material',segments:[4,4],color:'#999999',color_high:'#999999',roughness:1,metalness:0,emission:0};
   const scene={width:1280,height:720,camera:[camera,{...camera,at:12}],environment:{sky_top:'#808080',sky_bottom:'#808080',fog_color:'#000000',fog_density:0,light_color:'#FFFFFF',light_direction:[0,0,1],sun_size:.05,sun_strength:0,fill_strength:0},objects:[object]};
   const program={position:['(u-.5)*4.','(v-.5)*4.','0.'],color_mix:'0.'};
   const sample=detail=>{
    const r=RekindraWorld.createRenderer(scene,[detail===null?program:{...program,color_detail:detail}]);
    const c=document.createElement('canvas');c.width=1280;c.height=720;const x=c.getContext('2d');x.drawImage(r.render(0),0,0);
    const bytes=x.getImageData(450,200,380,320).data,png=c.toDataURL().split(',')[1];r.dispose();return{bytes,png};
   };
   const plain=sample(null),detailed=sample('.3*sin(u*80.)*sin(v*80.)');let changed=0,maxDelta=0;
   for(let i=0;i<plain.bytes.length;i+=4){const d=Math.abs(plain.bytes[i]-detailed.bytes[i]);if(d>2)changed++;maxDelta=Math.max(maxDelta,d)}
   const boundedDeltas=['1000.','-1000.'].map(expression=>{
    const extreme=sample(expression);let delta=0;
    for(let i=0;i<plain.bytes.length;i+=4)delta=Math.max(delta,Math.abs(plain.bytes[i]-extreme.bytes[i]));return delta;
   });
   return {changed,maxDelta,boundedDeltas,plain:plain.png,detailed:detailed.png};
  });
  for(const name of ['plain','detailed']){fs.writeFileSync(path.join(out,name+'.png'),Buffer.from(result[name],'base64'));delete result[name]}
  fs.writeFileSync(path.join(out,'result.json'),JSON.stringify(result,null,2));console.log(JSON.stringify(result));
  assert.ok(result.changed>10000,'Per-pixel detail was lost on a coarse mesh');
  assert.ok(result.maxDelta<60,'Subtle material detail changed brightness excessively');
  assert.ok(result.boundedDeltas.every(d=>d>2&&d<60),'Extreme detail was ignored or escaped its brightness clamp');
 }finally{await browser.close()}
})().catch(e=>{console.error(e);process.exitCode=1});
