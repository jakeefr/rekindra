const {chromium}=require(process.env.REKINDRA_PLAYWRIGHT_PATH||'playwright');
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
(async()=>{
 const fixtures=JSON.parse(fs.readFileSync(process.argv[2],'utf8')),out=path.resolve(process.argv[3]);
 fs.mkdirSync(out,{recursive:true});
 const browser=await chromium.launchPersistentContext(path.join(out,'profile'),{channel:'chrome',headless:true});
 try{
  const page=await browser.newPage(),errors=[];page.on('pageerror',e=>errors.push(String(e)));
  await page.setContent('');await page.addScriptTag({path:path.resolve('runtime/world.js')});
  const result=await page.evaluate(fixtures=>{
   const results={};
   for(const [name,f] of Object.entries(fixtures)){
    const s=f.scene,r=RekindraWorld.createRenderer(s,f.programs),c=document.createElement('canvas');
    c.width=s.width;c.height=s.height;const ctx=c.getContext('2d');
    ctx.drawImage(r.render(0),0,0);const png=c.toDataURL();
    const sample=p=>{const q=RekindraWorld.projectPoint(p,s.camera[0],s.width,s.height);return Array.from(ctx.getImageData(Math.round(q[0]),Math.round(q[1]),1,1).data)};
    const peaks=[.25,.5,.75].map(u=>sample([(u-.5)*8,0,0]));
    const troughs=[.125,.375,.625,.875].map(u=>sample([(u-.5)*8,0,0]));
    const cap=sample([0,2,0]),side=sample([0,1,2]);
    ctx.drawImage(r.render(3),0,0);const changed=png!==c.toDataURL();
    ctx.drawImage(r.render(0),0,0);const repeat=png===c.toDataURL();r.dispose();
    results[name]={peaks,troughs,cap,side,repeat,changed,png:png.split(',')[1]};
   }return results;
  },fixtures);
  // Save failing output too; a failed numeric assertion never discards evidence.
  for(const [name,row] of Object.entries(result))fs.writeFileSync(path.join(out,name+'.png'),Buffer.from(row.png,'base64'));
  fs.writeFileSync(path.join(out,'measurements.json'),JSON.stringify(result,(key,value)=>key==='png'?undefined:value,2));
  assert.deepEqual(errors,[],'No renderer errors');
  assert.equal(result.constantLegacy.png,result.constantPattern.png,'Constant optional pattern preserves equivalent legacy color');
  assert.equal(result.clampLow.png,result.black.png,'Pattern clamps below zero');
  assert.equal(result.clampHigh.png,result.constantLegacy.png,'Pattern clamps above one');
  assert.ok(result.legacy.troughs.every(p=>p[0]>150),'Control must demonstrate vertex aliasing');
  assert.ok(result.coarse.peaks.every(p=>p[0]>150),'Pattern peaks must be bright');
  assert.ok(result.coarse.troughs.every(p=>p[0]<15),'Per-pixel pattern must resolve troughs lost by vertex sampling');
  for(const key of ['peaks','troughs'])result.coarse[key].forEach((p,i)=>p.forEach((v,k)=>assert.ok(Math.abs(v-result.dense[key][i][k])<=2,'Pattern samples must be independent of tessellation')));
  for(const row of Object.values(result))assert.equal(row.repeat,true,'Exact 0 -> 3 -> 0 pixel repeat');
  assert.equal(result.animated.changed,true,'Time-dependent pattern must actually animate');
  assert.deepEqual(result.capPattern.cap,result.capLegacy.cap,'Caps retain vertex color_mix');
  assert.deepEqual(result.capCombined.cap,result.capLegacy.cap,'Combined pattern/color/bump detail leaves caps unchanged');
  assert.notEqual(result.combined.png,result.coarse.png,'Combined material/lighting fixture must produce different output');
  assert.ok(result.capPattern.side[0]>150&&result.capLegacy.side[0]<15,'Pattern changes the visible side but not the cap');
  console.log(JSON.stringify({passed:true,coarsePeaks:result.coarse.peaks,coarseTroughs:result.coarse.troughs,cap:result.capPattern.cap,side:result.capPattern.side}));
 }finally{await browser.close()}
})().catch(e=>{console.error(e);process.exitCode=1});
