const {chromium}=require(process.env.REKINDRA_PLAYWRIGHT_PATH||'playwright');
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
(async()=>{
 const fixtures=JSON.parse(fs.readFileSync(process.argv[2],'utf8')),out=path.resolve(process.argv[3]);fs.mkdirSync(out,{recursive:true});
 const browser=await chromium.launchPersistentContext(path.join(out,'profile'),{channel:'chrome',headless:true});
 try{
  const page=await browser.newPage(),errors=[];page.on('pageerror',e=>errors.push(String(e)));
  await page.setContent('');await page.addScriptTag({path:path.resolve(process.argv[4]||'runtime/world.js')});
  const result=await page.evaluate(fixtures=>{
   const results={};
   for(const [name,f] of Object.entries(fixtures)){
    const r=RekindraWorld.createRenderer(f.scene,f.programs),c=document.createElement('canvas');c.width=1280;c.height=720;const ctx=c.getContext('2d');
    ctx.drawImage(r.render(0),0,0);const png=c.toDataURL(),d=ctx.getImageData(0,0,1280,720).data;
    const center=d[(360*1280+640)*4];let sum=0,x2=0,y2=0;
    for(let y=0;y<720;y++)for(let x=0;x<1280;x++){const b=d[(y*1280+x)*4];sum+=b;x2+=b*(x-640)**2;y2+=b*(y-360)**2}
    ctx.drawImage(r.render(3),0,0);const changed=png!==c.toDataURL();ctx.drawImage(r.render(0),0,0);const repeat=png===c.toDataURL();r.dispose();
    results[name]={center,sum,xVariance:sum?x2/sum:0,yVariance:sum?y2/sum:0,repeat,changed,png:png.split(',')[1]};
   }return results;
  },fixtures);
  for(const [name,r]of Object.entries(result))fs.writeFileSync(path.join(out,name+'.png'),Buffer.from(r.png,'base64'));
  fs.writeFileSync(path.join(out,'measurements.json'),JSON.stringify(result,(k,v)=>k==='png'?undefined:v,2));
  assert.deepEqual(errors,[]);
  assert.equal(result.legacy.png,result.empty.png);assert.equal(result.legacy.png,result.off.png);
  assert.ok(result.litLegacy.sum>1000000,'Legacy compatibility control must be lit');
  assert.equal(result.litLegacy.png,result.litEmpty.png);assert.equal(result.litLegacy.png,result.litOff.png);
  assert.equal(result.legacy.center,0);assert.equal(result.behind.png,result.legacy.png);
  assert.ok(result.gloss.center>120,'Panel must produce bright specular reflection');
  assert.ok(result.diffuse.center>15,'Panel must illuminate nonmetal receiver without key/fill/ambient');
  assert.ok(result.gloss.yVariance>result.gloss.xVariance*3,'Tall panel must produce a tall highlight');
  assert.ok(result.rotated.xVariance>result.rotated.yVariance*3,'Rotation must turn the highlight');
  assert.ok(result.rough.xVariance>result.gloss.xVariance*2,'Rough reflection must broaden');
  assert.ok(result.rough.center<result.gloss.center-20,'Broadening must reduce peak');
  assert.equal(result.moving.changed,true);for(const r of Object.values(result))assert.equal(r.repeat,true);
  assert.ok(result.combined.sum>100000,'Four panels, polar directions, caps, bump, pattern and contact depth render together');
  console.log('Environment panel GPU controls passed');
 }finally{await browser.close()}
})().catch(e=>{console.error(e);process.exitCode=1});
