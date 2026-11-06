// Exercise actual production shaders: relief changes illumination, not geometry.
const {chromium}=require(process.env.REKINDRA_PLAYWRIGHT_PATH||'playwright');
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
(async()=>{
 const out=path.resolve(process.env.REKINDRA_BROWSER_OUTPUT||'.local/relief-regression');fs.mkdirSync(out,{recursive:true});
 const browser=await chromium.launchPersistentContext(path.join(out,'profile'),{channel:'chrome',headless:true});
 try{
  const page=await browser.newPage();await page.setContent('<body></body>');
  await page.addScriptTag({path:path.resolve(__dirname,'../runtime/world.js')});
  const result=await page.evaluate(()=>{
   const key={at:0,eye:[0,0,6],target:[0,0,0],fov:45};
   const scene={width:1280,height:720,camera:[key,{...key,at:12}],environment:{sky_top:'#808080',sky_bottom:'#808080',fog_color:'#000000',fog_density:0,light_color:'#FFFFFF',light_direction:[1,0,1],sun_size:.05,sun_strength:1,fill_strength:0},objects:[{id:'plane',segments:[4,4],color:'#999999',color_high:'#999999',roughness:.5,metalness:0,emission:0}]};
   const program={position:['(u-.5)*4.','(v-.5)*4.','0.'],color_mix:'0.'};
   function sample(bump,t=0){
    const r=RekindraWorld.createRenderer(scene,[bump===null?program:{...program,bump_detail:bump}]);
    const c=document.createElement('canvas');c.width=1280;c.height=720;const ctx=c.getContext('2d');ctx.drawImage(r.render(t),0,0);
    const bytes=ctx.getImageData(0,0,1280,720).data,png=c.toDataURL().split(',')[1];r.dispose();return{bytes,png};
   }
   const plain=sample(null),zero=sample('0.'),constant=sample('1000.'),relief=sample('.025*sin(u*80.+t)*sin(v*65.)'),later=sample('.025*sin(u*80.+t)*sin(v*65.)',2);
   function difference(a,b){let changed=0,max=0,outside=0;for(let y=0;y<720;y++)for(let x=0;x<1280;x++){const i=(y*1280+x)*4;let d=0;for(let c=0;c<3;c++)d=Math.max(d,Math.abs(a.bytes[i+c]-b.bytes[i+c]));if(d){changed++;if(x<300||x>980||y<50||y>670)outside++}max=Math.max(max,d)}return{changed,max,outside}}
   return{zero:difference(plain,zero),constant:difference(plain,constant),relief:difference(plain,relief),animated:difference(relief,later),images:{plain:plain.png,relief:relief.png}};
  });
  for(const [name,png] of Object.entries(result.images))fs.writeFileSync(path.join(out,name+'.png'),Buffer.from(png,'base64'));delete result.images;
  fs.writeFileSync(path.join(out,'result.json'),JSON.stringify(result,null,2));console.log(JSON.stringify(result));
  assert.equal(result.zero.changed,0);assert.equal(result.constant.changed,0);
  assert.ok(result.relief.changed>10000,'Relief failed to change lighting on a coarse mesh');
  assert.equal(result.relief.outside,0,'Relief changed pixels outside the surface');
  assert.ok(result.animated.changed>10000,'Animated relief failed to move highlights');
 }finally{await browser.close()}
})().catch(e=>{console.error(e);process.exitCode=1});
