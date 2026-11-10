// Object material_image on the software renderer (SwiftShader): the textured-material shader compiles and links, the
// surface carries the image's colour pattern where a plain surface is flat, crop selects the named region, repeat
// tiles it mirrored, strength 0 is the plain surface, and a missing image is refused. The image is a two-colour
// canvas made in the page: left half red, right half blue.
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
 const out=path.resolve(process.env.REKINDRA_BROWSER_OUTPUT||'.local/material_image');fs.mkdirSync(out,{recursive:true});
 const browser=await chromium.launchPersistentContext(path.join(out,'profile'),{channel:'chrome',headless:true,args:SOFTWARE_GL});
 try{
  const page=await browser.newPage();await page.setContent('');await page.addScriptTag({path:path.resolve('runtime/world.js')});
  await page.evaluate(instrument);
  const r=await page.evaluate(()=>{
   const W=320,H=180,camera={at:0,eye:[0,1.5,6],target:[0,1.5,0],fov:50};
   const env={sky_top:'#202830',sky_bottom:'#303840',fog_color:'#000000',fog_density:0,light_color:'#FFFFFF',light_direction:[.2,.6,1],sun_size:.05,sun_strength:2,fill_strength:.2,ambient_strength:.3};
   const source=document.createElement('canvas');source.width=64;source.height=64;
   const s=source.getContext('2d');s.fillStyle='#D02020';s.fillRect(0,0,32,64);s.fillStyle='#2040D0';s.fillRect(32,0,32,64);
   const images={photo:source};
   const panel={id:'panel',segments:[8,8],color:'#808080',color_high:'#808080',roughness:1,metalness:0,emission:0};
   // A quad facing the camera; u runs left to right across it.
   const P={panel:{position:['(u-.5)*4.','.5+v*2.','0.'],color_mix:'0.'}};
   const shot=material=>__capture({width:W,height:H,camera:[camera,{...camera,at:12}],environment:env,objects:[material?{...panel,material_image:material}:panel]},[P.panel],{images});
   const frames={plain:shot(null),full:shot({asset_id:'photo',crop:[0,0,1,1]}),left:shot({asset_id:'photo',crop:[0,0,.5,1]}),
    right:shot({asset_id:'photo',crop:[.5,0,.5,1]}),repeat:shot({asset_id:'photo',crop:[0,0,1,1],repeat:[2,1]}),
    off:shot({asset_id:'photo',crop:[0,0,1,1],strength:0})};
   let missing='';
   try{RekindraWorld.createRenderer({width:W,height:H,camera:[camera],environment:env,objects:[{...panel,material_image:{asset_id:'absent',crop:[0,0,1,1]}}]},[P.panel],{images}).dispose()}catch(e){missing=String(e.message)}
   const at=u=>RekindraWorld.projectPoint([(u-.5)*4,1.5,0],camera,W,H).map(Math.round);
   return {W,H,...frames,missing,pts:{u25:at(.25),u75:at(.75),u125:at(.125),u375:at(.375),u625:at(.625),u875:at(.875)},
    gl:{renderer:__gl.renderer,compiled:__gl.compiled,linked:__gl.linked,photoSources:__gl.sources.filter(t=>t.includes('materialImage')).length}};
  });
  const frames=['plain','full','left','right','repeat','off'];
  for(const k of frames)fs.writeFileSync(path.join(out,k+'.png'),Buffer.from(r[k].png,'base64'));
  const rgb=(img,[x,y])=>img.px.slice((y*r.W+x)*4,(y*r.W+x)*4+3);
  // Positive: red-dominant; negative: blue-dominant.
  const hue=(img,p)=>{const [R,,B]=rgb(img,p);return R-B};
  const diffMax=(a,b)=>{let m=0;for(let i=0;i<a.px.length;i++)if(i%4!==3)m=Math.max(m,Math.abs(a.px[i]-b.px[i]));return m};
  const spread=img=>{const L=[];for(let i=0;i<img.px.length;i+=4)L.push(img.px[i]+img.px[i+1]+img.px[i+2]);const m=L.reduce((a,b)=>a+b,0)/L.length;return Math.sqrt(L.reduce((a,b)=>a+(b-m)**2,0)/L.length)};
  const p=r.pts,metrics={renderer:r.gl.renderer,shaders:r.gl.compiled.length,programs:r.gl.linked.length,photoSources:r.gl.photoSources,
   glErrors:frames.map(k=>r[k].glError),lost:frames.filter(k=>r[k].lost),frameSpread:spread(r.full),pts:p,
   plain:[hue(r.plain,p.u25),hue(r.plain,p.u75)],plainLeftRight:diffMax({px:rgb(r.plain,p.u25)},{px:rgb(r.plain,p.u75)}),
   full:[hue(r.full,p.u25),hue(r.full,p.u75)],left:[hue(r.left,p.u25),hue(r.left,p.u75)],right:[hue(r.right,p.u25),hue(r.right,p.u75)],
   repeat:[p.u125,p.u375,p.u625,p.u875].map(q=>hue(r.repeat,q)),strengthZeroVsPlain:diffMax(r.off,r.plain),missing:r.missing};
  fs.writeFileSync(path.join(out,'result.json'),JSON.stringify(metrics,null,2));console.log(metrics);
  assert.match(r.gl.renderer,/SwiftShader/i,'Must run on the SwiftShader software renderer');
  assert.ok(r.gl.compiled.length>0&&r.gl.compiled.every(Boolean),'Every shader must compile');
  assert.ok(r.gl.linked.length>0&&r.gl.linked.every(Boolean),'Every program must link');
  assert.ok(r.gl.photoSources>0,'The material image shader must have been compiled');
  assert.deepEqual(metrics.glErrors,frames.map(()=>0),'No GL error after any frame');
  assert.deepEqual(metrics.lost,[],'No context loss');
  assert.ok(metrics.frameSpread>10,'Frame must not be blank');
  assert.ok(metrics.plainLeftRight<=6&&metrics.plain.every(h=>Math.abs(h)<=6),'Control: the plain surface is flat grey');
  assert.ok(metrics.full[0]>60&&metrics.full[1]<-60,'Full crop: the surface carries the image, red on the left and blue on the right');
  assert.ok(metrics.left.every(h=>h>60),'Crop of the left half must show only red');
  assert.ok(metrics.right.every(h=>h<-60),'Crop of the right half must show only blue');
  const [a,b,c,d]=metrics.repeat;
  assert.ok(a>60&&b<-60&&c<-60&&d>60,'repeat [2,1] must tile the image mirrored: red, blue, blue, red');
  assert.ok(metrics.strengthZeroVsPlain<=2,'strength 0 must leave the plain surface');
  assert.match(metrics.missing,/not embedded/,'A material image whose source is absent must be refused');
 }finally{await browser.close()}
})().catch(e=>{console.error(e);process.exitCode=1});
