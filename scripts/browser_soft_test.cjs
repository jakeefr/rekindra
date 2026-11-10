// Object soft (glow surfaces only) on the software renderer (SwiftShader): the feathered glow shader compiles and
// links, the light fades gradually toward the surface edges where a plain glow surface stops at a hard silhouette,
// the core is unchanged, and breakup alters only the fading edge.
const {chromium}=require(process.env.REKINDRA_PLAYWRIGHT_PATH||'playwright');
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
const SOFTWARE_GL=['--use-angle=swiftshader','--enable-unsafe-swiftshader'];
// Records every shader source, compile and link result, and each WebGL2 context the runtime creates.
function instrument(){
 const P=WebGL2RenderingContext.prototype,log=window.__gl={sources:[],compiled:[],linked:[],contexts:[]};
 const probe=document.createElement('canvas').getContext('webgl2'),info=probe&&probe.getExtension('WEBGL_debug_renderer_info');
 log.renderer=probe?(info?probe.getParameter(info.UNMASKED_RENDERER_WEBGL):probe.getParameter(probe.RENDERER)):'no webgl2';
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
 const out=path.resolve(process.env.REKINDRA_BROWSER_OUTPUT||'.local/soft');fs.mkdirSync(out,{recursive:true});
 const browser=await chromium.launchPersistentContext(path.join(out,'profile'),{channel:'chrome',headless:true,args:SOFTWARE_GL});
 try{
  const page=await browser.newPage();await page.setContent('');await page.addScriptTag({path:path.resolve('runtime/world.js')});
  await page.evaluate(instrument);
  const r=await page.evaluate(()=>{
   const W=320,H=180,camera={at:0,eye:[0,1.5,6],target:[0,1.5,0],fov:50};
   const env={sky_top:'#080A10',sky_bottom:'#0C1018',fog_color:'#000000',fog_density:0,light_color:'#FFFFFF',light_direction:[.2,.6,1],sun_size:.05,sun_strength:2,fill_strength:.2,ambient_strength:.3};
   const light={id:'light',segments:[24,24],color:'#6080C0',color_high:'#6080C0',roughness:1,metalness:0,emission:0,glow:1};
   // A quad facing the camera; u runs left to right, v bottom to top. "away" puts it behind the camera for the background.
   const P={light:{position:['(u-.5)*4.','.5+v*2.','0.'],color_mix:'0.'},away:{position:['(u-.5)*4.','.5+v*2.','40.'],color_mix:'0.'}};
   const shot=(object,program)=>__capture({width:W,height:H,camera:[camera,{...camera,at:12}],environment:env,objects:[object]},[program]);
   const frames={background:shot(light,P.away),hard:shot(light,P.light),soft:shot({...light,soft:{u:.6,v:.6}},P.light),
    broken:shot({...light,soft:{u:.6,v:.6,breakup:.8}},P.light)};
   const at=(u,v)=>RekindraWorld.projectPoint([(u-.5)*4,.5+v*2,0],camera,W,H).map(Math.round);
   return {W,H,...frames,pts:{edge:at(.03,.5),inner:at(.15,.5),centre:at(.5,.5),left:at(0,.5),core:[at(.4,.6),at(.6,.4)],rim:[at(.02,.8),at(.98,.2)]},
    gl:{renderer:__gl.renderer,compiled:__gl.compiled,linked:__gl.linked,softSources:__gl.sources.filter(s=>s.includes('feather')).length}};
  });
  const frames=['background','hard','soft','broken'];
  for(const k of frames)fs.writeFileSync(path.join(out,k+'.png'),Buffer.from(r[k].png,'base64'));
  const idx=([x,y])=>(y*r.W+x)*4,lum=(img,i)=>img.px[i]+img.px[i+1]+img.px[i+2];
  // Light the glow adds over the background at a point.
  const added=(img,p)=>lum(img,idx(p))-lum(r.background,idx(p));
  // Largest jump between neighbouring pixels along the row through the centre, from outside the quad to its middle.
  const y=r.pts.centre[1],jump=img=>{let m=0;for(let x=Math.max(1,r.pts.left[0]-10);x<=r.pts.centre[0];x++)m=Math.max(m,Math.abs(lum(img,idx([x,y]))-lum(img,idx([x-1,y]))));return m};
  // Pixels where breakup changed the frame, inside the core box and inside the rim box.
  const changed=([[ax,ay],[bx,by]])=>{let n=0;for(let yy=Math.min(ay,by);yy<=Math.max(ay,by);yy++)for(let x=Math.min(ax,bx);x<=Math.max(ax,bx);x++)if(Math.abs(lum(r.broken,idx([x,yy]))-lum(r.soft,idx([x,yy])))>6)n++;return n};
  const spread=img=>{const L=[];for(let i=0;i<img.px.length;i+=4)L.push(lum(img,i));const m=L.reduce((a,b)=>a+b,0)/L.length;return Math.sqrt(L.reduce((a,b)=>a+(b-m)**2,0)/L.length)};
  const ratio=(img,p)=>added(img,p)/Math.max(1,added(img,r.pts.centre));
  const metrics={renderer:r.gl.renderer,shaders:r.gl.compiled.length,programs:r.gl.linked.length,softSources:r.gl.softSources,
   glErrors:frames.map(k=>r[k].glError),lost:frames.filter(k=>r[k].lost),frameSpread:spread(r.soft),pts:r.pts,
   hardCentre:added(r.hard,r.pts.centre),softCentre:added(r.soft,r.pts.centre),
   hardEdge:ratio(r.hard,r.pts.edge),softEdge:ratio(r.soft,r.pts.edge),softInner:ratio(r.soft,r.pts.inner),
   hardJump:jump(r.hard),softJump:jump(r.soft),breakupCore:changed(r.pts.core),breakupRim:changed(r.pts.rim)};
  fs.writeFileSync(path.join(out,'result.json'),JSON.stringify(metrics,null,2));console.log(metrics);
  assert.match(r.gl.renderer,/SwiftShader/i,'Must run on the SwiftShader software renderer');
  assert.ok(r.gl.compiled.length>0&&r.gl.compiled.every(Boolean),'Every shader must compile');
  assert.ok(r.gl.linked.length>0&&r.gl.linked.every(Boolean),'Every program must link');
  assert.ok(r.gl.softSources>0,'The soft-edge glow shader must have been compiled');
  assert.deepEqual(metrics.glErrors,frames.map(()=>0),'No GL error after any frame');
  assert.deepEqual(metrics.lost,[],'No context loss');
  assert.ok(metrics.frameSpread>10,'Frame must not be blank');
  assert.ok(metrics.hardCentre>60,'Control: the glow surface must add visible light');
  assert.ok(metrics.hardEdge>.8,'Control: without soft the glow keeps its strength up to the edge');
  assert.ok(metrics.softEdge<.15,'soft must fade the light almost out at the edge');
  assert.ok(metrics.softInner>.1&&metrics.softInner<.7,'soft must fade gradually: part strength partway in');
  assert.ok(Math.abs(metrics.softCentre-metrics.hardCentre)<=6,'soft must leave the core unchanged');
  assert.ok(metrics.softJump*3<metrics.hardJump,'soft must replace the hard silhouette step with a gradual edge');
  assert.equal(metrics.breakupCore,0,'breakup must not change the core');
  assert.ok(metrics.breakupRim>50,'breakup must split the fading edge');
 }finally{await browser.close()}
})().catch(e=>{console.error(e);process.exitCode=1});
