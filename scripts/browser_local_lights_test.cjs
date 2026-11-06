const {chromium}=require(process.env.REKINDRA_PLAYWRIGHT_PATH||'playwright');
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
(async()=>{
 const fixture=JSON.parse(fs.readFileSync(process.argv[2],'utf8')),out=path.resolve(process.argv[3]);fs.mkdirSync(out,{recursive:true});
 const browser=await chromium.launchPersistentContext(path.join(out,'profile'),{channel:'chrome',headless:true});
 try{
  const page=await browser.newPage();await page.setContent('');await page.addScriptTag({path:path.resolve('runtime/world.js')});
  const result=await page.evaluate(f=>{
   function capture(lights){
    f.scene.environment.point_lights=lights;
    const r=RekindraWorld.createRenderer(f.scene,f.programs),c=document.createElement('canvas');c.width=1280;c.height=720;
    const x=c.getContext('2d');x.drawImage(r.render(0),0,0);r.dispose();
    const sample=p=>{const q=RekindraWorld.projectPoint(p,f.scene.camera[0],1280,720);return Array.from(x.getImageData(Math.round(q[0]),Math.round(q[1]),1,1).data)};
    return {near:sample([0,0,0]),far:sample([3,0,0]),outside:sample([5,0,0]),png:c.toDataURL().split(',')[1]};
   }
   const light={position:[0,1,0],color:'#FF2000',intensity:10,range:4};
   const result={off:capture([]),on:capture([light]),zero:capture([{...light,intensity:0}]),center:capture([{...light,position:[0,0,0]}]),four:capture(Array.from({length:4},()=>({...light,intensity:1}))),combined:capture([{...light,intensity:4}]),lastOnly:capture(Array.from({length:4},(_,i)=>({...light,intensity:i===3?10:0})))};
   f.scene.objects[0].metalness=1;result.metal=capture([light]);return result;
  },fixture);
  fs.writeFileSync(path.join(out,'receiver.png'),Buffer.from(result.on.png,'base64'));
  for(const v of Object.values(result))delete v.png;
  fs.writeFileSync(path.join(out,'result.json'),JSON.stringify(result,null,2));console.log(result);
  assert.ok(result.on.near[0]>100,'Local light must illuminate nearby receiver');
  assert.ok(result.on.near[0]>result.on.far[0]*2,'Illumination must fall with distance');
  assert.ok(result.on.near[0]>result.on.near[1]*2,'Light color must affect receiver');
  assert.deepEqual(result.on.outside,result.off.outside,'Outside range must remain unlit');
  assert.deepEqual(result.zero,result.off,'Zero intensity must match no lights');
  assert.equal(result.center.near[3],255,'Coincident source must preserve opaque coverage');
  assert.ok(result.four.near[0]>100,'All four light uniforms must compile and illuminate');
  assert.deepEqual(result.four.near,result.combined.near,'Four lights must sum before tone mapping');
  assert.deepEqual(result.lastOnly.near,result.on.near,'Fourth light must illuminate independently');
  assert.ok(result.metal.near[0]>10,'Metallic receiver must receive a local specular response');
 }finally{await browser.close()}
})().catch(e=>{console.error(e);process.exitCode=1});
