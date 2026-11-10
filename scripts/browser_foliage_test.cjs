// Object foliage on the software renderer (SwiftShader): the leaf shader compiles and links, the surface is cut into
// leaf gaps that show the sky behind it, leaf cells vary in colour, and higher density leaves fewer gaps. A plain
// surface is the control: solid and uniform.
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
 const out=path.resolve(process.env.REKINDRA_BROWSER_OUTPUT||'.local/foliage');fs.mkdirSync(out,{recursive:true});
 const browser=await chromium.launchPersistentContext(path.join(out,'profile'),{channel:'chrome',headless:true,args:SOFTWARE_GL});
 try{
  const page=await browser.newPage();await page.setContent('');await page.addScriptTag({path:path.resolve('runtime/world.js')});
  await page.evaluate(instrument);
  const r=await page.evaluate(()=>{
   const W=320,H=180,camera={at:0,eye:[0,1.5,6],target:[0,1.5,0],fov:50};
   const env={sky_top:'#A0C8F0',sky_bottom:'#D0E0F0',fog_color:'#000000',fog_density:0,light_color:'#FFFFFF',light_direction:[.2,.6,1],sun_size:.05,sun_strength:2,fill_strength:.2,ambient_strength:.3};
   const canopy={id:'canopy',segments:[16,16],color:'#204818',color_high:'#78B040',roughness:1,metalness:0,emission:0};
   // The same surface placed behind the camera: a frame of sky only, to recognise leaf gaps.
   const P={canopy:{position:['(u-.5)*4.','v*3.','0.'],color_mix:'0.'},away:{position:['(u-.5)*4.','v*3.','40.'],color_mix:'0.'}};
   const shot=(object,program)=>__capture({width:W,height:H,camera:[camera,{...camera,at:12}],environment:env,objects:[object]},[program]);
   const frames={sky:shot(canopy,P.away),plain:shot(canopy,P.canopy),
    leaves:shot({...canopy,foliage:{leaf_size:.25,density:.5,variation:.8}},P.canopy),
    sparse:shot({...canopy,foliage:{leaf_size:.25,density:.3,variation:.8}},P.canopy),
    dense:shot({...canopy,foliage:{leaf_size:.25,density:1,variation:.8}},P.canopy)};
   const proj=p=>RekindraWorld.projectPoint(p,camera,W,H).map(Math.round);
   return {W,H,...frames,box:[proj([-1.7,2.7,0]),proj([1.7,.3,0])],
    gl:{renderer:__gl.renderer,compiled:__gl.compiled,linked:__gl.linked,leafSources:__gl.sources.filter(s=>s.includes('leafCover')).length}};
  });
  const frames=['sky','plain','leaves','sparse','dense'];
  for(const k of frames)fs.writeFileSync(path.join(out,k+'.png'),Buffer.from(r[k].png,'base64'));
  // Inside the projected surface, away from its outline.
  const [[x0,y0],[x1,y1]]=r.box;
  const region=img=>{let gaps=0,n=0;const L=[];
   for(let y=y0;y<=y1;y++)for(let x=x0;x<=x1;x++){const i=(y*r.W+x)*4;n++;
    if(Math.max(...[0,1,2].map(k=>Math.abs(img.px[i+k]-r.sky.px[i+k])))<=3)gaps++;else L.push(img.px[i]+img.px[i+1]+img.px[i+2]);}
   const m=L.reduce((a,b)=>a+b,0)/Math.max(1,L.length);
   return {gapFraction:gaps/n,leafSpread:Math.sqrt(L.reduce((a,b)=>a+(b-m)**2,0)/Math.max(1,L.length))}};
  const spread=img=>{const L=[];for(let i=0;i<img.px.length;i+=4)L.push(img.px[i]+img.px[i+1]+img.px[i+2]);const m=L.reduce((a,b)=>a+b,0)/L.length;return Math.sqrt(L.reduce((a,b)=>a+(b-m)**2,0)/L.length)};
  const metrics={renderer:r.gl.renderer,shaders:r.gl.compiled.length,programs:r.gl.linked.length,leafSources:r.gl.leafSources,
   glErrors:frames.map(k=>r[k].glError),lost:frames.filter(k=>r[k].lost),frameSpread:spread(r.leaves),box:r.box,
   plain:region(r.plain),leaves:region(r.leaves),sparse:region(r.sparse),dense:region(r.dense)};
  fs.writeFileSync(path.join(out,'result.json'),JSON.stringify(metrics,null,2));console.log(metrics);
  assert.match(r.gl.renderer,/SwiftShader/i,'Must run on the SwiftShader software renderer');
  assert.ok(r.gl.compiled.length>0&&r.gl.compiled.every(Boolean),'Every shader must compile');
  assert.ok(r.gl.linked.length>0&&r.gl.linked.every(Boolean),'Every program must link');
  assert.ok(r.gl.leafSources>0,'The foliage shader must have been compiled');
  assert.deepEqual(metrics.glErrors,frames.map(()=>0),'No GL error after any frame');
  assert.deepEqual(metrics.lost,[],'No context loss');
  assert.ok(metrics.frameSpread>10,'Frame must not be blank');
  assert.ok(metrics.plain.gapFraction<.01,'Control: the plain surface must be solid');
  assert.ok(metrics.leaves.gapFraction>.05&&metrics.leaves.gapFraction<.8,'Foliage must cut leaf gaps through which the sky shows, without erasing the surface');
  assert.ok(metrics.leaves.leafSpread>metrics.plain.leafSpread+8,'Foliage must vary leaf colour and facing across the surface');
  assert.ok(metrics.dense.gapFraction<metrics.sparse.gapFraction-.05,'Higher density must leave fewer gaps');
 }finally{await browser.close()}
})().catch(e=>{console.error(e);process.exitCode=1});
