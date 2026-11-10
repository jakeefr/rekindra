// Soft highlights: off by default (shader text unchanged), a bright glow core keeps its gradient when on,
// and the emitter mask marks glow surfaces only. REKINDRA_BASELINE_WORLD may name an older world.js to compare against.
const {chromium}=require(process.env.REKINDRA_PLAYWRIGHT_PATH||'playwright');
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
const run=async(browser,runtime)=>{
  const page=await browser.newPage();await page.setContent('');
  await page.addScriptTag({content:'window.__shaders=[];const s=WebGL2RenderingContext.prototype.shaderSource;WebGL2RenderingContext.prototype.shaderSource=function(h,t){window.__shaders.push(t);return s.call(this,h,t)}'});
  await page.addScriptTag({path:runtime});
  const r=await page.evaluate(()=>{
    const W=640,H=360,camera={at:0,eye:[0,1.5,6],target:[0,1.5,0],fov:40};
    const env={sky_top:'#05070C',sky_bottom:'#0A0D14',fog_color:'#000000',fog_density:0,light_color:'#FFFFFF',light_direction:[1,1,.3],sun_size:.05,sun_strength:.5,fill_strength:.1,ambient_strength:.1};
    const ground={id:'ground',segments:[4,4],color:'#303030',color_high:'#303030',roughness:1,metalness:0,emission:0};
    const ball={id:'ball',segments:[48,24],color:'#FFD8A0',color_high:'#FFD8A0',roughness:1,metalness:0,emission:0,glow:6};
    const P={ground:{position:['(u-.5)*30.','0.','(v-.5)*30.'],color_mix:'0.'},
      ball:{position:['.8*cos(u*2.*pi)*sin(v*pi)','1.5+.8*cos(v*pi)','.8*sin(u*2.*pi)*sin(v*pi)'],color_mix:'0.'}};
    function capture(objs,atmosphere,wantMask){
      const environment=atmosphere===undefined?env:{...env,atmosphere};
      const scene={width:W,height:H,camera:[camera,{...camera,at:6}],environment,objects:objs};
      window.__shaders.length=0;
      const rr=RekindraWorld.createRenderer(scene,objs.map(o=>P[o.id])),c=document.createElement('canvas');c.width=W;c.height=H;
      const x=c.getContext('2d');x.drawImage(rr.render(1),0,0);
      const mask=wantMask&&rr.emitterMask?rr.emitterMask(1):undefined;rr.dispose();
      return{px:Array.from(x.getImageData(0,0,W,H).data),png:c.toDataURL().split(',')[1],shaders:window.__shaders.join('\n'),
        mask:mask&&{width:mask.width,height:mask.height,data:Array.from(mask.data)}};
    }
    const centre=RekindraWorld.projectPoint([0,1.5,.8],camera,W,H).map(Math.round);
    return{W,H,centre,
      plain:capture([ground,{...ball,glow:undefined}],undefined,true),glowPlain:capture([ground,ball],undefined,true),
      bloom:capture([ground,ball],{bloom:.8,halo:.6}),soft:capture([ground,ball],{bloom:.8,halo:.6,highlights:'soft'},true),
      softOnly:capture([ground,ball],{highlights:'soft'})};
  });
  await page.close();return r;
};
(async()=>{
  const out=path.resolve(process.env.REKINDRA_BROWSER_OUTPUT||'.local/highlights');fs.mkdirSync(out,{recursive:true});
  const browser=await chromium.launchPersistentContext(path.join(out,'profile'),{channel:'chrome',headless:true});
  try{
    const r=await run(browser,path.resolve('runtime/world.js'));
    for(const k of ['glowPlain','bloom','soft','softOnly'])fs.writeFileSync(path.join(out,k+'.png'),Buffer.from(r[k].png,'base64'));
    const at=(x,y)=>(y*r.W+x)*4,white=img=>{let n=0;for(let i=0;i<img.px.length;i+=4)if(img.px[i]===255&&img.px[i+1]===255&&img.px[i+2]===255)n++;return n};
    const row=img=>{const s=new Set();for(let x=r.centre[0]-60;x<=r.centre[0]+60;x++){const i=at(x,r.centre[1]);s.add(img.px[i]+','+img.px[i+1]+','+img.px[i+2])}return s.size};
    const core=img=>img.px.slice(at(...r.centre),at(...r.centre)+3);
    const knee=Math.log(5).toFixed(8);
    const metrics={whiteBloom:white(r.bloom),whiteSoft:white(r.soft),whiteSoftOnly:white(r.softOnly),whitePlainGlow:white(r.glowPlain),
      coreBloom:core(r.bloom),coreSoft:core(r.soft),rowLevelsBloom:row(r.bloom),rowLevelsSoft:row(r.soft)};
    fs.writeFileSync(path.join(out,'result.json'),JSON.stringify(metrics,null,2));console.log(metrics);
    for(const k of ['plain','glowPlain','bloom'])assert.ok(!r[k].shaders.includes(knee),`${k}: soft tone code must not be emitted without the option`);
    assert.ok(r.soft.shaders.includes(knee),'Soft highlights must emit the shoulder');
    assert.ok(metrics.whiteBloom>200,'Control: the bright glow ball must clip to white with the standard curve');
    assert.ok(metrics.whiteSoft<metrics.whiteBloom/10,'Soft highlights must leave far fewer pixels clipped to white');
    assert.ok(metrics.whiteSoftOnly<metrics.whitePlainGlow/10,'Soft highlights alone must also roll the core off');
    assert.ok(metrics.rowLevelsSoft>metrics.rowLevelsBloom,'The soft core must keep more distinct levels across its width');
    // The mask: null without glow surfaces, lit on the ball, dark in the corner.
    assert.equal(r.plain.mask,null,'No glow surface means no emitter mask');
    for(const m of [r.glowPlain.mask,r.soft.mask]){
      const mx=Math.round(r.centre[0]*m.width/r.W),my=Math.round(r.centre[1]*m.height/r.H);
      assert.ok(m.data[my*m.width+mx]>=64,'The emitter mask must cover the glow ball');
      assert.ok(m.data[5*m.width+5]<64,'The emitter mask must leave the empty corner dark');
    }
    const baseline=process.env.REKINDRA_BASELINE_WORLD;
    if(baseline){
      const b=await run(browser,path.resolve(baseline));let diff=0;
      for(const k of ['plain','glowPlain','bloom']){
        assert.equal(r[k].shaders,b[k].shaders,`${k}: shader text must match the baseline runtime`);
        for(let i=0;i<r[k].px.length;i++)if(r[k].px[i]!==b[k].px[i])diff++;
      }
      console.log({baselineIdentical:diff===0,differingBytes:diff});assert.equal(diff,0,'Scenes without the option must render pixel-identically');
    }
  }finally{await browser.close()}
})().catch(e=>{console.error(e);process.exitCode=1});
