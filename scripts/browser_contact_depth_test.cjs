const {chromium}=require(process.env.REKINDRA_PLAYWRIGHT_PATH||'playwright');
const fs=require('fs'),path=require('path'),assert=require('node:assert/strict');
(async()=>{
 const fixture=JSON.parse(fs.readFileSync(process.argv[2],'utf8')),out=path.resolve(process.argv[3]);fs.mkdirSync(out,{recursive:true});
 const browser=await chromium.launchPersistentContext(path.join(out,'profile'),{channel:'chrome',headless:true});
 try{
  const page=await browser.newPage();await page.setContent('');await page.addScriptTag({path:path.resolve('runtime/world.js')});
  const result=await page.evaluate(f=>{
   function capture(strength,mode='ambient',wall=true){
    const s=JSON.parse(JSON.stringify(f.scene)),programs=wall?f.programs:f.programs.slice(0,1);
    if(!wall)s.objects=s.objects.slice(0,1);
    if(strength!==null)s.environment.occlusion_strength=strength;s.environment.occlusion_radius=1;
    if(mode!=='ambient'){s.environment.sky_top=s.environment.sky_bottom='#000000';s.environment.ambient_strength=0;}
    if(mode==='direct'){s.environment.sun_strength=1;s.environment.light_direction=[0,4,2];}
    if(mode==='emission')for(const o of s.objects)o.emission=1;
    const r=RekindraWorld.createRenderer(s,programs),c=document.createElement('canvas');c.width=s.width;c.height=s.height;const ctx=c.getContext('2d');
    ctx.drawImage(r.render(0),0,0);const png=c.toDataURL();r.render(3);ctx.drawImage(r.render(0),0,0);const repeat=png===c.toDataURL();r.dispose();
    const sample=p=>{const q=RekindraWorld.projectPoint(p,s.camera[0],s.width,s.height);return Array.from(ctx.getImageData(Math.round(q[0]),Math.round(q[1]),1,1).data)};
    return {near:sample([0,0,.2]),far:sample([0,0,3]),plane:[-.8,0,.8].flatMap(x=>[.2,1,3].map(z=>sample([x,0,z]))),png:png.split(',')[1],repeat};
   }
   return {off:capture(null),zero:capture(0),on:capture(1),flatOff:capture(0,'ambient',false),flatOn:capture(1,'ambient',false),directOff:capture(0,'direct'),directOn:capture(1,'direct'),emissionOff:capture(0,'emission'),emissionOn:capture(1,'emission')};
  },fixture);
  assert.equal(result.off.png,result.zero.png,'Omitted and zero full images must match');
  assert.equal(result.directOff.png,result.directOn.png,'Direct-only full images must match');
  assert.equal(result.emissionOff.png,result.emissionOn.png,'Emissive-only full images must match');
  for(const [name,row] of Object.entries(result)){fs.writeFileSync(path.join(out,name+'.png'),Buffer.from(row.png,'base64'));delete row.png;}
  fs.writeFileSync(path.join(out,'result.json'),JSON.stringify(result,null,2));console.log(JSON.stringify(result));
  assert.deepEqual(result.off,result.zero,'Omitted and zero must match');
  assert.ok(result.off.near[0]-result.on.near[0]>=8,'Nearby wall must occlude indirect light');
  assert.ok(Math.abs(result.off.far[0]-result.on.far[0])<=4,'Distant floor must remain unchanged');
  result.flatOff.plane.forEach((p,i)=>p.forEach((v,k)=>assert.ok(Math.abs(v-result.flatOn.plane[i][k])<=2,'Flat plane must not self-occlude')));
  assert.ok(result.directOff.near[0]>20,'Direct-only fixture must actually be illuminated');
  assert.deepEqual(result.directOff,result.directOn,'Direct light must not be darkened');
  assert.ok(result.emissionOff.near[0]>20,'Emission-only fixture must actually emit');
  assert.deepEqual(result.emissionOff,result.emissionOn,'Emission must not be darkened');
  for(const row of Object.values(result))assert.equal(row.repeat,true,'Repeat render must match');
 }finally{await browser.close()}
})().catch(e=>{console.error(e);process.exitCode=1});
