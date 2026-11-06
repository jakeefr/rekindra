const {chromium}=require(process.env.REKINDRA_PLAYWRIGHT_PATH||'playwright');
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
(async()=>{
 const fixtures=JSON.parse(fs.readFileSync(process.argv[2],'utf8')),out=path.resolve(process.argv[3]);fs.mkdirSync(out,{recursive:true});
 const browser=await chromium.launchPersistentContext(path.join(out,'profile'),{channel:'chrome',headless:true});
 try{
  const page=await browser.newPage(),errors=[];page.on('pageerror',e=>errors.push(String(e)));
  await page.setContent('');await page.addScriptTag({path:path.resolve(process.argv[4]||'runtime/world.js')});
  const result=await page.evaluate(fixtures=>{
   const alive={Texture:new Set(),Framebuffer:new Set(),Renderbuffer:new Set()},proto=WebGL2RenderingContext.prototype;
   for(const[k,set]of Object.entries(alive)){const create=proto['create'+k],remove=proto['delete'+k];proto['create'+k]=function(...a){const r=create.apply(this,a);if(r)set.add(r);return r};proto['delete'+k]=function(r){set.delete(r);return remove.call(this,r)}}
   const results={};
   for(const[name,f]of Object.entries(fixtures)){
    const r=RekindraWorld.createRenderer(f.scene,f.programs),c=document.createElement('canvas');c.width=1280;c.height=720;const ctx=c.getContext('2d');ctx.drawImage(r.render(0),0,0);const png=c.toDataURL();
    const sample=p=>{const q=RekindraWorld.projectPoint(p,f.scene.camera[0],1280,720);return Array.from(ctx.getImageData(Math.round(q[0]),Math.round(q[1]),1,1).data)};
    const reflectedRed=sample([-1.2,name==='raised'?-.5:-1.5,0]),reflectedBlue=sample([1.2,name==='raised'?-.8:-1.8,0]);
    const d=ctx.getImageData(0,400,1280,320).data;let edgeEnergy=0;
    for(let y=0;y<320;y++)for(let x=1;x<1280;x++)for(let k=0;k<3;k++){const i=(y*1280+x)*4+k;edgeEnergy+=(d[i]-d[i-4])**2}
    ctx.drawImage(r.render(3),0,0);const changed=png!==c.toDataURL();ctx.drawImage(r.render(0),0,0);const repeat=png===c.toDataURL();r.dispose();
    results[name]={reflectedRed,reflectedBlue,edgeEnergy,changed,repeat,leaks:Object.fromEntries(Object.entries(alive).map(([k,s])=>[k,s.size])),png:png.split(',')[1]};
   }return results;
  },fixtures);
  for(const[name,row]of Object.entries(result))fs.writeFileSync(path.join(out,name+'.png'),Buffer.from(row.png,'base64'));
  fs.writeFileSync(path.join(out,'measurements.json'),JSON.stringify(result,(k,v)=>k==='png'?undefined:v,2));
  assert.deepEqual(errors,[]);assert.equal(result.legacy.png,result.off.png);
  assert.ok(result.legacy.reflectedRed[0]<5,'Baseline has no object reflection');
  assert.ok(result.sharp.reflectedRed[0]>150&&result.sharp.reflectedRed[1]<10,'Red object reflected at geometric mirror location');
  assert.ok(result.sharp.reflectedBlue[2]>150&&result.sharp.reflectedBlue[0]<10,'Blue reflection keeps horizontal handedness');
  assert.equal(result.sharp.png,result.clipped.png,'Geometry below plane must not leak into reflection');
  assert.ok(result.raised.reflectedRed[0]>150,'Nonzero plane height must mirror around its actual height');
  assert.ok(result.blurred.edgeEnergy<result.sharp.edgeEnergy*.9,'Bounded blur must soften reflection edges');
  assert.equal(result.under.png,result.underOff.png,'Camera below reflector uses original path');
  assert.ok(result.combined.reflectedRed[0]>100,'Contact depth and environment panels coexist with mirror');
  for(const row of Object.values(result)){assert.equal(row.repeat,true,'Exact 0 -> 3 -> 0 repeat');assert.deepEqual(row.leaks,{Texture:0,Framebuffer:0,Renderbuffer:0},'All GPU targets disposed')}
  assert.equal(result.sharp.changed,true);assert.equal(result.cameraMotion.changed,true);
  console.log('Planar reflection GPU controls passed');
 }finally{await browser.close()}
})().catch(e=>{console.error(e);process.exitCode=1});
