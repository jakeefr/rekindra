// Diagnostic: compare actual float32 uniform bits and raw GPU pixels across tasks.
const {chromium}=require(process.env.REKINDRA_PLAYWRIGHT_PATH||'playwright');
const fs=require('node:fs'),path=require('node:path'),{pathToFileURL}=require('node:url');
(async()=>{
 const out=path.resolve(process.argv[3]);fs.mkdirSync(out,{recursive:true});
 const mode=process.argv[4]||'baseline';
 const context=await chromium.launchPersistentContext(path.join(out,'profile'),{channel:'chrome',headless:true,
  args:mode==='software'?['--use-angle=swiftshader','--enable-unsafe-swiftshader']:[]});
 const original=fs.readFileSync(path.resolve('runtime/world.js'),'utf8');
 const needle='if(Array.isArray(value))gl.uniform3fv(loc,value);else gl.uniform1f(loc,value)';
 if(!original.includes(needle))throw Error('Uniform instrumentation anchor changed');
 let source=original.replace(needle,`if(globalThis.uniformTrace){const f=new Float32Array(Array.isArray(value)?value:[value]);globalThis.uniformTrace.push([name,...new Uint32Array(f.buffer)])} ${needle}`);
 if(mode==='no-dither')source=source.replace('const owned=[];let lost=false;','gl.disable(gl.DITHER);const owned=[];let lost=false;');
 if(mode==='explicit-target'){
  // Diagnostic only: remove browser-owned scene attachments from the draw path.
  if(!source.includes('antialias:true'))throw Error('Antialias anchor changed');
  source=source.replace('antialias:true','antialias:false'); // Single-sample blit needs a single-sample destination.
  source=source.replace('const owned=[];let lost=false;',`const owned=[];let lost=false;
const target=gl.createFramebuffer(),color=gl.createRenderbuffer(),depth=gl.createRenderbuffer();
gl.bindFramebuffer(gl.FRAMEBUFFER,target);gl.bindRenderbuffer(gl.RENDERBUFFER,color);
gl.renderbufferStorage(gl.RENDERBUFFER,gl.RGBA8,canvas.width,canvas.height);
gl.framebufferRenderbuffer(gl.FRAMEBUFFER,gl.COLOR_ATTACHMENT0,gl.RENDERBUFFER,color);
gl.bindRenderbuffer(gl.RENDERBUFFER,depth);gl.renderbufferStorage(gl.RENDERBUFFER,gl.DEPTH_COMPONENT24,canvas.width,canvas.height);
gl.framebufferRenderbuffer(gl.FRAMEBUFFER,gl.DEPTH_ATTACHMENT,gl.RENDERBUFFER,depth);
if(gl.checkFramebufferStatus(gl.FRAMEBUFFER)!==gl.FRAMEBUFFER_COMPLETE)throw Error('Diagnostic framebuffer incomplete');
gl.bindFramebuffer(gl.FRAMEBUFFER,null);`);
  source=source.replace('gl.disable(gl.POLYGON_OFFSET_FILL);gl.bindFramebuffer(gl.FRAMEBUFFER,null);','gl.disable(gl.POLYGON_OFFSET_FILL);gl.bindFramebuffer(gl.FRAMEBUFFER,target);');
  source=source.replace("gl.bindVertexArray(null);if(gl.getError()",`gl.bindFramebuffer(gl.READ_FRAMEBUFFER,target);gl.bindFramebuffer(gl.DRAW_FRAMEBUFFER,null);
gl.blitFramebuffer(0,0,canvas.width,canvas.height,0,0,canvas.width,canvas.height,gl.COLOR_BUFFER_BIT,gl.NEAREST);
gl.bindFramebuffer(gl.FRAMEBUFFER,null);gl.bindVertexArray(null);if(gl.getError()`);
  source=source.replace('dispose(){for(const s of surfaces)', 'dispose(){gl.deleteRenderbuffer(color);gl.deleteRenderbuffer(depth);gl.deleteFramebuffer(target);for(const s of surfaces)');
 }
 const results=[];
 try{for(const warm of [false,true])for(let trial=0;trial<10;trial++){
  const page=await context.newPage();await page.goto(pathToFileURL(path.resolve(process.argv[2])).href);await page.waitForFunction(()=>globalThis.rekindra?.ready);
  await page.addScriptTag({content:source});
  await page.evaluate(warm=>{
   window.r=RekindraWorld.createRenderer(rekindra.scene,rekindra.data.programs);
   const gl=r.canvas.getContext('webgl2'),ext=gl.getExtension('WEBGL_debug_renderer_info');
   window.backend=ext?gl.getParameter(ext.UNMASKED_RENDERER_WEBGL):gl.getParameter(gl.RENDERER);
   const c=document.createElement('canvas');c.width=1280;c.height=720;const x=c.getContext('2d');
   window.capture=t=>{globalThis.uniformTrace=[];r.render(t);const gl=r.canvas.getContext('webgl2'),pixels=new Uint8Array(1280*720*4);gl.readPixels(0,0,1280,720,gl.RGBA,gl.UNSIGNED_BYTE,pixels);x.drawImage(r.canvas,0,0);return{pixels,copy:x.getImageData(0,0,1280,720).data,uniforms:JSON.stringify(uniformTrace)}};
   if(warm){capture(0);capture(1);capture(2.5)}
   window.a=capture(1);capture(2.5);
  },warm);
  const row=await page.evaluate(()=>{capture(.1);const b=capture(1);let changed=0,maxDelta=0,copyChanged=0;const samples=[];for(let i=0;i<a.pixels.length;i++){const d=Math.abs(a.pixels[i]-b.pixels[i]);if(d){changed++;if(samples.length<8)samples.push([i,a.pixels[i],b.pixels[i]])}maxDelta=Math.max(maxDelta,d);copyChanged+=a.copy[i]!==b.copy[i]}const sameUniforms=a.uniforms===b.uniforms;r.dispose();return{changed,maxDelta,copyChanged,sameUniforms,samples,backend}});
  results.push({warm,trial,...row});await page.close();
 }}finally{await context.close()}
 fs.writeFileSync(path.join(out,'result.json'),JSON.stringify(results,null,2));
 console.log(JSON.stringify(results));
})().catch(e=>{console.error(e);process.exitCode=1});
