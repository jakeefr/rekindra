// environment.atmosphere on the software renderer (SwiftShader): the post-process programs compile and link, a null
// atmosphere reproduces the plain frame, haze pulls distant surfaces toward haze_color more than near ones, haze_height
// keeps haze off upward rays, vignette darkens only the frame edge, grain is visible and the same at the same time.
const {chromium}=require(process.env.REKINDRA_PLAYWRIGHT_PATH||'playwright');
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
const SOFTWARE_GL=['--use-angle=swiftshader','--enable-unsafe-swiftshader'];
// Records every shader source, compile and link result, and each WebGL2 context the runtime creates.
function instrument(){
 const P=WebGL2RenderingContext.prototype,log=window.__gl={sources:[],compiled:[],linked:[],contexts:[]};
 const probe=document.createElement('canvas').getContext('webgl2'),info=probe&&probe.getExtension('WEBGL_debug_renderer_info');
 log.renderer=probe?(info?probe.getParameter(info.UNMASKED_RENDERER_WEBGL):probe.getParameter(probe.RENDERER)):'no webgl2';
 log.floatTargets=!!(probe&&probe.getExtension('EXT_color_buffer_float'));
 const source=P.shaderSource;P.shaderSource=function(s,text){log.sources.push(text);return source.call(this,s,text)};
 const shaderParameter=P.getShaderParameter;P.getShaderParameter=function(s,n){const r=shaderParameter.call(this,s,n);if(n===this.COMPILE_STATUS)log.compiled.push(!!r);return r};
 const programParameter=P.getProgramParameter;P.getProgramParameter=function(p,n){const r=programParameter.call(this,p,n);if(n===this.LINK_STATUS)log.linked.push(!!r);return r};
 const getContext=HTMLCanvasElement.prototype.getContext;
 HTMLCanvasElement.prototype.getContext=function(type,options){const g=getContext.call(this,type,options);if(type==='webgl2'&&g)log.contexts.push(g);return g};
 // Renders one frame and reports the GL error state of the context that drew it.
 window.__capture=(scene,programs,options)=>{
  const first=log.contexts.length,rr=RekindraWorld.createRenderer(scene,programs,options),frame=rr.render(0),g=log.contexts[first];
  const glError=g.getError(),lost=g.isContextLost(),c=document.createElement('canvas');c.width=scene.width;c.height=scene.height;
  const x=c.getContext('2d');x.drawImage(frame,0,0);rr.dispose();
  return {px:Array.from(x.getImageData(0,0,c.width,c.height).data),png:c.toDataURL().split(',')[1],glError,lost};
 };
}
(async()=>{
 const out=path.resolve(process.env.REKINDRA_BROWSER_OUTPUT||'.local/atmosphere');fs.mkdirSync(out,{recursive:true});
 const browser=await chromium.launchPersistentContext(path.join(out,'profile'),{channel:'chrome',headless:true,args:SOFTWARE_GL});
 try{
  const page=await browser.newPage();await page.setContent('');await page.addScriptTag({path:path.resolve('runtime/world.js')});
  await page.evaluate(instrument);
  const r=await page.evaluate(()=>{
   const W=320,H=180,camera={at:0,eye:[0,2,8],target:[0,1,-10],fov:50};
   const env={sky_top:'#101820',sky_bottom:'#182028',fog_color:'#000000',fog_density:0,light_color:'#FFFFFF',light_direction:[.3,1,.6],sun_size:.05,sun_strength:2,fill_strength:.2,ambient_strength:.3};
   const ground={id:'ground',segments:[8,8],color:'#606060',color_high:'#606060',roughness:1,metalness:0,emission:0};
   // An atmosphere switches the renderer off MSAA; a black glow ghost behind the camera does the same for the plain
   // control, so every frame takes the same antialiasing path and adds no light.
   const ghost={id:'ghost',segments:[8,2],color:'#000000',color_high:'#000000',roughness:1,metalness:0,emission:0,glow:1};
   const P={ground:{position:['(u-.5)*80.','0.','8.-v*80.'],color_mix:'0.'},ghost:{position:['cos(u*2.*pi)','v','40.+sin(u*2.*pi)'],color_mix:'0.'}};
   const shot=atmosphere=>{const e=atmosphere?{...env,atmosphere}:env;
    return __capture({width:W,height:H,camera:[camera,{...camera,at:12}],environment:e,objects:[ground,ghost]},[P.ground,P.ghost])};
   const haze={haze_color:'#C8B490',haze_density:.04};
   const proj=p=>RekindraWorld.projectPoint(p,camera,W,H).map(Math.round);
   const frames={none:shot(null),nullAtmo:shot({haze_density:0,bloom:0,halo:0,grain:0,vignette:0}),haze:shot(haze),
    hazeHeight:shot({...haze,haze_height:1,haze_floor:0}),vignette:shot({vignette:.8}),
    grain:shot({grain:.12}),grainAgain:shot({grain:.12})};
   return {W,H,...frames,gl:{renderer:__gl.renderer,floatTargets:__gl.floatTargets,compiled:__gl.compiled,linked:__gl.linked,
     atmosphereSources:__gl.sources.filter(s=>s.includes('atmoHazeColor')).length},
    pts:{near:proj([0,0,4]),far:proj([0,0,-45]),sky:[Math.round(W/2),3],corner:[3,H-4],centre:[Math.round(W/2),Math.round(H/2)]}};
  });
  const frames=['none','nullAtmo','haze','hazeHeight','vignette','grain','grainAgain'];
  for(const k of frames)fs.writeFileSync(path.join(out,k+'.png'),Buffer.from(r[k].png,'base64'));
  const at=([x,y])=>(y*r.W+x)*4,rgb=(img,p)=>img.px.slice(at(p),at(p)+3),lum=(img,p)=>rgb(img,p).reduce((a,b)=>a+b,0);
  const hazeRGB=[0xC8,0xB4,0x90],dist=(a,b)=>Math.hypot(a[0]-b[0],a[1]-b[1],a[2]-b[2]);
  // Fraction of the way from the plain pixel to haze_color.
  const toward=(img,p,ctrl=r.none)=>1-dist(rgb(img,p),hazeRGB)/dist(rgb(ctrl,p),hazeRGB);
  const diff=(a,b)=>{let max=0,n=0;const rows=new Set();for(let i=0;i<a.px.length;i++){if(i%4===3)continue;const d=Math.abs(a.px[i]-b.px[i]);if(d>max)max=d;if(d>2){n++;rows.add(Math.floor(i/4/r.W))}}
   const y=[...rows].sort((p,q)=>p-q);return{max,over2:n,rows:y.length?[y[0],y[y.length-1]]:[]}};
  const spread=img=>{const L=[];for(let i=0;i<img.px.length;i+=4)L.push(img.px[i]+img.px[i+1]+img.px[i+2]);const m=L.reduce((a,b)=>a+b,0)/L.length;return Math.sqrt(L.reduce((a,b)=>a+(b-m)**2,0)/L.length)};
  const metrics={renderer:r.gl.renderer,floatTargets:r.gl.floatTargets,shaders:r.gl.compiled.length,programs:r.gl.linked.length,atmosphereSources:r.gl.atmosphereSources,
   glErrors:frames.map(k=>r[k].glError),lost:frames.filter(k=>r[k].lost),frameSpread:spread(r.haze),
   nullVsNone:diff(r.nullAtmo,r.none),hazeNear:toward(r.haze,r.pts.near),hazeFar:toward(r.haze,r.pts.far),
   hazeSky:toward(r.haze,r.pts.sky),hazeHeightSky:toward(r.hazeHeight,r.pts.sky),
   vignetteCorner:lum(r.vignette,r.pts.corner)/Math.max(1,lum(r.nullAtmo,r.pts.corner)),vignetteCentre:lum(r.vignette,r.pts.centre)-lum(r.nullAtmo,r.pts.centre),
   grainVsNull:diff(r.grain,r.nullAtmo).over2,grainRepeat:diff(r.grain,r.grainAgain).max,pts:r.pts};
  fs.writeFileSync(path.join(out,'result.json'),JSON.stringify(metrics,null,2));console.log(metrics);
  assert.match(r.gl.renderer,/SwiftShader/i,'Must run on the SwiftShader software renderer');
  assert.ok(r.gl.compiled.length>0&&r.gl.compiled.every(Boolean),'Every shader must compile');
  assert.ok(r.gl.linked.length>0&&r.gl.linked.every(Boolean),'Every program must link');
  assert.ok(r.gl.atmosphereSources>0,'The atmosphere composite shader must have been compiled');
  assert.deepEqual(metrics.glErrors,frames.map(()=>0),'No GL error after any frame');
  assert.deepEqual(metrics.lost,[],'No context loss');
  assert.ok(metrics.frameSpread>10,'Frame must not be blank');
  assert.ok(metrics.nullVsNone.max<=4,'Control: an atmosphere with every effect at zero must reproduce the plain frame');
  assert.ok(metrics.hazeFar>.5,'Haze must pull a distant surface well toward haze_color');
  assert.ok(metrics.hazeNear<.3,'Haze must leave a near surface mostly unchanged');
  assert.ok(metrics.hazeFar>metrics.hazeNear+.3,'Haze must grow with distance');
  assert.ok(metrics.hazeSky>.5,'Control: without haze_height an upward sky ray is hazed');
  assert.ok(metrics.hazeHeightSky<metrics.hazeSky-.3,'haze_height must keep haze off upward rays');
  assert.ok(metrics.vignetteCorner<.8,'Vignette must darken the frame corner');
  assert.ok(Math.abs(metrics.vignetteCentre)<=6,'Vignette must leave the frame centre unchanged');
  assert.ok(metrics.grainVsNull>1000,'Grain must visibly change pixels');
  assert.equal(metrics.grainRepeat,0,'Grain must be identical for the same time');
 }finally{await browser.close()}
})().catch(e=>{console.error(e);process.exitCode=1});
