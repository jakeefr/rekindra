const {chromium}=require(process.env.REKINDRA_PLAYWRIGHT_PATH||'playwright');
const fs=require('fs'),path=require('path'),assert=require('node:assert/strict');
(async()=>{
 const out=path.resolve(process.env.REKINDRA_BROWSER_OUTPUT||'.local/facing-normals');fs.mkdirSync(out,{recursive:true});
 const browser=await chromium.launchPersistentContext(path.join(out,'profile'),{channel:'chrome',headless:true});
 try{
  const page=await browser.newPage();await page.setContent('');
  const source=fs.readFileSync('runtime/world.js','utf8');
  // Expose actual final shader normal; red=down, green=up. Geometry/shaders unchanged.
  const diagnostic=source.replace('pixel=vec4(displayColor(lit),1.);','pixel=vec4(N.y<0.?1.:0.,N.y>=0.?1.:0.,0.,1.);');
  assert.notEqual(diagnostic,source);await page.addScriptTag({content:diagnostic});
  const results=await page.evaluate(()=>{
   const results=[];
   for(const below of [false,true])for(const flat of [false,true]){
    const sign=below?-1:1;
    const camera={at:0,eye:[0,sign*1,8],target:[0,0,-12],fov:40};
    const object={id:'sheet',segments:[16,28],color:'#FFFFFF',color_high:'#FFFFFF',roughness:.7,metalness:0,emission:0,...(flat?{shading:'flat'}:{})};
    const scene={width:1280,height:720,camera:[camera,{...camera,at:12}],environment:{sky_top:'#000000',sky_bottom:'#000000',fog_color:'#000000',fog_density:0,light_color:'#FFFFFF',light_direction:[0,1,0],sun_size:.05,sun_strength:1},objects:[object]};
    const program={position:['(u-.5)*40.','.18*sin((-35.+v*40.)*1.7)','-35.+v*40.'],color_mix:'0.'};
    const renderer=RekindraWorld.createRenderer(scene,[program]);
    const c=document.createElement('canvas');c.width=1280;c.height=720;const ctx=c.getContext('2d');
    const capture=t=>{ctx.drawImage(renderer.render(t),0,0);return ctx.getImageData(0,0,1280,720).data};
    const bytes=capture(0),png=c.toDataURL().split(',')[1];capture(3);const repeat=capture(0);
    let wrong=0,measured=0,different=0;
    for(let i=0;i<bytes.length;i+=4){if(bytes[i]+bytes[i+1]===255&&bytes[i+2]===0){measured++;if(below?bytes[i+1]===255:bytes[i]===255)wrong++}for(let j=0;j<4;j++)if(bytes[i+j]!==repeat[i+j])different++}
    results.push({name:(below?'below':'above')+'-'+(flat?'flat':'smooth'),measured,wrong,different,png});renderer.dispose();
   }
   return results;
  });
  for(const r of results){fs.writeFileSync(path.join(out,r.name+'.png'),Buffer.from(r.png,'base64'));delete r.png}
  fs.writeFileSync(path.join(out,'result.json'),JSON.stringify(results,null,2));console.log(JSON.stringify(results));
  for(const r of results){assert.ok(r.measured>10000,r.name+' lacks coverage');assert.equal(r.wrong,0,r.name+' inverted visible normals');assert.equal(r.different,0,r.name+' nonrepeatable')}
  const real=await browser.newPage();await real.setContent('');await real.addScriptTag({content:source});
  const mirrored=await real.evaluate(()=>{
   const results=[];for(const mode of ['smooth','flat','cap']){
   const camera={at:0,eye:[0,3,7],target:[0,0,0],fov:45};
   const material={segments:[8,8],color:'#FF0000',color_high:'#FF0000',roughness:1,metalness:0,emission:0};
   const scene={width:1280,height:720,camera:[camera,{...camera,at:12}],environment:{sky_top:'#000000',sky_bottom:'#000000',fog_color:'#000000',fog_density:0,light_color:'#FFFFFF',light_direction:[0,0,1],sun_size:.05,sun_strength:1,fill_strength:0,ambient_strength:0},objects:[{...material,id:'sheet',...(mode==='flat'?{shading:'flat'}:{}),...(mode==='cap'?{caps:['v0','v1']}:{})},{...material,id:'mirror',position:{x:'0',y:'0',z:'0'},reflection:{strength:1,blur:0}}]};
   const programs=[{position:mode==='cap'?['cos(u*2.*pi)','2.+sin(u*2.*pi)','v*.2']:['(u-.5)*2.','1.+v*2.','0.'],color_mix:'0.'},{position:['(u-.5)*12.','0.','(v-.5)*12.'],color_mix:'0.'}];
   const r=RekindraWorld.createRenderer(scene,programs),c=document.createElement('canvas');c.width=1280;c.height=720;const x=c.getContext('2d');x.drawImage(r.render(0),0,0);
   const sample=p=>{const q=RekindraWorld.projectPoint(p,camera,1280,720);return [...x.getImageData(Math.round(q[0]),Math.round(q[1]),1,1).data]};
   const z=mode==='cap'?.2:0;const result={mode,direct:sample([0,2,z]),reflected:sample([0,-2,z]),png:c.toDataURL().split(',')[1]};r.dispose();results.push(result); }return results;
  });
  for(const r of mirrored){fs.writeFileSync(path.join(out,'mirror-'+r.mode+'.png'),Buffer.from(r.png,'base64'));delete r.png}
  fs.writeFileSync(path.join(out,'mirror-result.json'),JSON.stringify(mirrored,null,2));console.log(JSON.stringify(mirrored));
  for(const r of mirrored){assert.ok(r.direct[0]>180,r.mode+' direct lit control missing');assert.ok(r.reflected[0]>180,r.mode+' mirrored lit normal inverted')}
 }finally{await browser.close()}
})().catch(e=>{console.error(e);process.exitCode=1});
