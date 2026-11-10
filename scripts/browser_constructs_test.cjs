// Construction fields (feathers, drape, ring) on the software renderer (SwiftShader): the shader math the Python
// compiler emits for each compiles and links, each part adds light as a glow form, the ring keeps its hole, the
// cloth flares toward the ground, and the feather array spreads as its open expression rises over time.
const {chromium}=require(process.env.REKINDRA_PLAYWRIGHT_PATH||'playwright');
const {execFileSync}=require('node:child_process');
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
const SOFTWARE_GL=['--use-angle=swiftshader','--enable-unsafe-swiftshader'];
const COMPILE=`
import json, sys
sys.path.insert(0, '.')
from rekindra_core.worlds import compile_surface
def part(segments, position, **field):
    out = compile_surface(dict({'id': 'part', 'segments': segments, 'color_mix': '0', 'position': dict(zip('xyz', position))}, **field))
    return {k: out[k] for k in ('position', 'color_mix', 'definitions')}
print(json.dumps({
    'feathers': part([48, 8], ['feather_x', 'feather_y+2.8', 'feather_z'], feathers={'count': 12, 'spread': 2.4, 'length': 1.2,
                     'curve': .6, 'fan': 1.0, 'taper': .5, 'overlap': .6, 'open': 'clamp(t/8,0,1)'}),
    'drape': part([48, 16], ['drape_x', 'drape_y+.2', 'drape_z'], drape={'height': 2.2, 'top_radius': .2, 'hem_radius': 1.0,
                  'pool': .6, 'folds': 8, 'fold_depth': .15}),
    'ring': part([48, 12], ['ring_x', 'ring_y+1.5', 'ring_z'], ring={'radius': .9, 'thickness': .15, 'tilt': 1.5708}),
}))`;
function instrument(){
 const P=WebGL2RenderingContext.prototype,log=window.__gl={compiled:[],linked:[],contexts:[]};
 const probe=document.createElement('canvas').getContext('webgl2'),info=probe&&probe.getExtension('WEBGL_debug_renderer_info');
 log.renderer=probe?(info?probe.getParameter(info.UNMASKED_RENDERER_WEBGL):probe.getParameter(probe.RENDERER)):'no webgl2';
 const shaderParameter=P.getShaderParameter;P.getShaderParameter=function(s,n){const r=shaderParameter.call(this,s,n);if(n===this.COMPILE_STATUS)log.compiled.push(!!r);return r};
 const programParameter=P.getProgramParameter;P.getProgramParameter=function(p,n){const r=programParameter.call(this,p,n);if(n===this.LINK_STATUS)log.linked.push(!!r);return r};
 const getContext=HTMLCanvasElement.prototype.getContext;
 HTMLCanvasElement.prototype.getContext=function(type,options){const g=getContext.call(this,type,options);if(type==='webgl2'&&g)log.contexts.push(g);return g};
 window.__capture=(scene,programs,time)=>{
  const first=log.contexts.length,rr=RekindraWorld.createRenderer(scene,programs),frame=rr.render(time),g=log.contexts[first];
  const glError=g.getError(),lost=g.isContextLost(),c=document.createElement('canvas');c.width=scene.width;c.height=scene.height;
  const x=c.getContext('2d');x.drawImage(frame,0,0);rr.dispose();
  return {px:Array.from(x.getImageData(0,0,c.width,c.height).data),png:c.toDataURL().split(',')[1],glError,lost};
 };
}
(async()=>{
 const out=path.resolve(process.env.REKINDRA_BROWSER_OUTPUT||'.local/constructs');fs.mkdirSync(out,{recursive:true});
 const programs=JSON.parse(execFileSync(process.env.REKINDRA_PYTHON||'python',['-c',COMPILE],{cwd:path.resolve('.'),encoding:'utf8'}));
 const browser=await chromium.launchPersistentContext(path.join(out,'profile'),{channel:'chrome',headless:true,args:SOFTWARE_GL});
 try{
  const page=await browser.newPage();await page.setContent('');await page.addScriptTag({path:path.resolve('runtime/world.js')});
  await page.evaluate(instrument);
  const r=await page.evaluate(P=>{
   const W=320,H=180,camera={at:0,eye:[0,1.5,6],target:[0,1.5,0],fov:50};
   const env={sky_top:'#080A10',sky_bottom:'#0C1018',fog_color:'#000000',fog_density:0,light_color:'#FFFFFF',light_direction:[.2,.6,1],sun_size:.05,sun_strength:2,fill_strength:.2,ambient_strength:.3};
   const light=segments=>({id:'part',segments,color:'#6080C0',color_high:'#6080C0',roughness:1,metalness:0,emission:0,glow:1});
   const away={position:['(u-.5)*4.','.5+v*2.','40.'],color_mix:'0.'};
   const shot=(segments,program,time,extra)=>__capture({width:W,height:H,duration:12,camera:[camera,{...camera,at:12}],environment:env,objects:[{...light(segments),...extra}]},[program],time);
   const at=p=>RekindraWorld.projectPoint(p,camera,W,H).map(Math.round);
   return {W,H,background:shot([24,24],away,0),folded:shot([48,8],P.feathers,0,{feathers:{count:12}}),open:shot([48,8],P.feathers,10,{feathers:{count:12}}),
    webbed:shot([48,8],P.feathers,10),softRing:shot([48,12],P.ring,0,{ring:{},soft:{u:.4,v:.4}}),
    softOpen:shot([48,8],P.feathers,10,{feathers:{count:12},soft:{u:.6,v:.5}}),drape:shot([48,16],P.drape,0,{drape:{}}),ring:shot([48,12],P.ring,0,{ring:{}}),
    pts:{ringCentre:at([0,1.5,0]),ringRim:at([.9,1.5,0]),hem:at([0,.3,0]),top:at([0,2.3,0])},
    gl:{renderer:__gl.renderer,compiled:__gl.compiled,linked:__gl.linked}};
  },programs);
  const frames=['background','folded','open','webbed','softOpen','softRing','drape','ring'];
  for(const k of frames)fs.writeFileSync(path.join(out,k+'.png'),Buffer.from(r[k].png,'base64'));
  const idx=(x,y)=>(y*r.W+x)*4,lum=(img,i)=>img.px[i]+img.px[i+1]+img.px[i+2];
  const added=(img,x,y)=>lum(img,idx(x,y))-lum(r.background,idx(x,y));
  // Lit pixels, and the left and right extent of the light, over the whole frame or one row.
  const lit=(img,row)=>{let n=0,lo=r.W,hi=-1;for(let y=row??0;y<=(row??r.H-1);y++)for(let x=0;x<r.W;x++)if(added(img,x,y)>20){n++;lo=Math.min(lo,x);hi=Math.max(hi,x)}return {n,width:hi<lo?0:hi-lo+1}};
  const metrics={renderer:r.gl.renderer,shaders:r.gl.compiled.length,programs:r.gl.linked.length,
   glErrors:frames.map(k=>r[k].glError),lost:frames.filter(k=>r[k].lost),pts:r.pts,
   folded:lit(r.folded),open:lit(r.open),softOpen:lit(r.softOpen),drape:lit(r.drape),ring:lit(r.ring),
   hemWidth:lit(r.drape,r.pts.hem[1]).width,topWidth:lit(r.drape,r.pts.top[1]).width,
   webbed:lit(r.webbed),ringCentre:added(r.ring,...r.pts.ringCentre),ringRim:added(r.ring,...r.pts.ringRim),
   softRingSeam:added(r.softRing,...r.pts.ringRim)};
  fs.writeFileSync(path.join(out,'result.json'),JSON.stringify(metrics,null,2));console.log(metrics);
  assert.match(r.gl.renderer,/SwiftShader/i,'Must run on the SwiftShader software renderer');
  assert.ok(r.gl.compiled.length>0&&r.gl.compiled.every(Boolean),'Every shader must compile');
  assert.ok(r.gl.linked.length>0&&r.gl.linked.every(Boolean),'Every program must link');
  assert.deepEqual(metrics.glErrors,frames.map(()=>0),'No GL error after any frame');
  assert.deepEqual(metrics.lost,[],'No context loss');
  assert.ok(metrics.folded.n>100,'The folded feather array must be visible');
  assert.ok(metrics.open.width>metrics.folded.width*1.5,'The feather array must spread as open rises over time');
  assert.ok(metrics.softOpen.n>50&&metrics.softOpen.n<metrics.open.n,'soft must feather the cards and leave them visible');
  assert.ok(metrics.open.n<metrics.webbed.n*.97,'The cells joining one feather card to the next must not be drawn');
  assert.ok(metrics.softRingSeam>20,'soft must not cut a notch at the seam of a ring');
  assert.ok(metrics.drape.n>500,'The draped cloth must be visible');
  assert.ok(metrics.hemWidth>metrics.topWidth*2,'The cloth must flare from its top to a hem on the ground');
  assert.ok(metrics.ring.n>100&&metrics.ringRim>20,'The ring must be visible along its rim');
  assert.ok(metrics.ringCentre<10,'The ring must keep its hole');
 }finally{await browser.close()}
})().catch(e=>{console.error(e);process.exitCode=1});
