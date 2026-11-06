// Real GPU tests. Fixture contains compiler output, never hand-authored shader transforms.
const {chromium}=require(process.env.REKINDRA_PLAYWRIGHT_PATH||'playwright');
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
(async()=>{
 const out=path.resolve('.local/assembly-loop/gpu');fs.mkdirSync(out,{recursive:true});
 const fixture=JSON.parse(fs.readFileSync(process.argv[2],'utf8'));
 const browser=await chromium.launchPersistentContext(path.join(out,'profile'),{channel:'chrome',headless:true});
 try{
  const page=await browser.newPage();await page.setContent('<body></body>');await page.addScriptTag({path:path.resolve('runtime/world.js')});
  const result=await page.evaluate(({chain,move,bounded})=>{
   const gl=document.createElement('canvas').getContext('webgl2');
   function shader(type,source){const s=gl.createShader(type);gl.shaderSource(s,source);gl.compileShader(s);if(!gl.getShaderParameter(s,gl.COMPILE_STATUS))throw Error(gl.getShaderInfoLog(s));return s}
   const p=gl.createProgram();
   gl.attachShader(p,shader(gl.VERTEX_SHADER,`#version 300 es\nprecision highp float;layout(location=0)in vec3 inputPoint;uniform float t;out vec3 outputPoint;void main(){vec3 p=inputPoint;${chain}outputPoint=p;gl_Position=vec4(p,1.);}`));
   gl.attachShader(p,shader(gl.FRAGMENT_SHADER,'#version 300 es\nprecision highp float;out vec4 color;void main(){color=vec4(1.);}'));
   gl.transformFeedbackVaryings(p,['outputPoint'],gl.INTERLEAVED_ATTRIBS);gl.linkProgram(p);
   if(!gl.getProgramParameter(p,gl.LINK_STATUS))throw Error(gl.getProgramInfoLog(p));gl.useProgram(p);
   const input=gl.createBuffer();gl.bindBuffer(gl.ARRAY_BUFFER,input);gl.bufferData(gl.ARRAY_BUFFER,new Float32Array([0,1,0,1,1,0,0,1,0]),gl.STATIC_DRAW);gl.enableVertexAttribArray(0);gl.vertexAttribPointer(0,3,gl.FLOAT,false,0,0);
   const output=gl.createBuffer();gl.bindBuffer(gl.TRANSFORM_FEEDBACK_BUFFER,output);gl.bufferData(gl.TRANSFORM_FEEDBACK_BUFFER,36,gl.DYNAMIC_READ);gl.bindBufferBase(gl.TRANSFORM_FEEDBACK_BUFFER,0,output);
   const samples=[];gl.enable(gl.RASTERIZER_DISCARD);
   for(const t of [0,Math.PI/2]){gl.uniform1f(gl.getUniformLocation(p,'t'),t);gl.beginTransformFeedback(gl.POINTS);gl.drawArrays(gl.POINTS,0,3);gl.endTransformFeedback();const a=new Float32Array(9);gl.getBufferSubData(gl.TRANSFORM_FEEDBACK_BUFFER,0,a);samples.push(Array.from(a));}
   const key={at:0,eye:[0,0,6],target:[0,0,0],fov:45};
   const material={id:'tube',segments:[32,8],color:'#EF7822',color_high:'#EF7822',roughness:.8,metalness:0,emission:0};
   const scene={width:1280,height:720,camera:[key,{...key,at:12}],environment:{sky_top:'#164583',sky_bottom:'#164583',fog_color:'#000000',fog_density:0,light_color:'#FFFFFF',light_direction:[1,1,2],sun_size:.05,sun_strength:1,fill_strength:.2},objects:[material]};
   const program={position:['cos(u*2.*pi)','sin(u*2.*pi)','v*2.-1.'],color_mix:'0.',assembly:move};
   function sample(caps,t=0){material.caps=caps;const r=RekindraWorld.createRenderer(scene,[program]);const c=document.createElement('canvas');c.width=1280;c.height=720;const x=c.getContext('2d');x.drawImage(r.render(t),0,0);const rgb=Array.from(x.getImageData(640,360,1,1).data);r.dispose();return rgb}
   const caps={open:sample([]),closed:sample(['v0','v1']),moved:sample(['v0','v1'],4)};
   scene.camera=scene.camera.map(k=>({...k,eye:[0,4,10]}));scene.environment.light_direction=[0,1,0];
   material.instances=[{offset:[0,0,0],scale:[1,1,1]}];
   scene.objects=[{...material,id:'floor',caps:[],instances:undefined,color:'#FFFFFF',color_high:'#FFFFFF'},material];
   const programs=[{position:['(u-.5)*12.','0.','(v-.5)*12.'],color_mix:'0.'},{position:['cos(u*2.*pi)','1.5+v*1.5','sin(u*2.*pi)'],color_mix:'0.',assembly:move}];
   function shadow(caps){material.caps=caps;const r=RekindraWorld.createRenderer(scene,programs);const c=document.createElement('canvas');c.width=1280;c.height=720;const x=c.getContext('2d');x.drawImage(r.render(2),0,0);const [px,py]=RekindraWorld.projectPoint([2,0,0],scene.camera[0],1280,720);const v=x.getImageData(Math.round(px),Math.round(py),1,1).data[0];r.dispose();return v}
   const shadows={open:shadow([]),closed:shadow(['v1'])};
   scene.camera=scene.camera.map(k=>({...k,eye:[6,0,6],target:[6,0,0]}));
   scene.environment.light_direction=[1,1,2];
   scene.objects=[{...material,instances:undefined,caps:['v0','v1']}];
   const r=RekindraWorld.createRenderer(scene,[{position:['120.+10.*cos(u*2.*pi)','sin(u*2.*pi)','v*2.-1.'],color_mix:'0.',assembly:bounded}]);
   const c=document.createElement('canvas');c.width=1280;c.height=720;const x=c.getContext('2d');x.drawImage(r.render(0),0,0);
   const finalClamp=Array.from(x.getImageData(640,360,1,1).data);r.dispose();
   return {samples,caps,shadow:shadows,finalClamp};
  },fixture);
  fs.writeFileSync(path.join(out,'result.json'),JSON.stringify(result,null,2));console.log(JSON.stringify(result));
  const expected=[[2,1,0,4,1,0,2,1,0],[2,1,0,2,3,0,2,1,0]];
  result.samples.forEach((a,i)=>a.forEach((v,j)=>assert.ok(Math.abs(v-expected[i][j])<1e-5,'Shared transformed joint/rotation differs')));
  assert.ok(result.caps.open[2]>result.caps.open[0]);assert.ok(result.caps.closed[0]>result.caps.closed[2]+40);
  assert.deepEqual(result.caps.moved,result.caps.open,'Caps did not follow assembly');
  assert.ok(result.shadow.open>result.shadow.closed+40,'Assembly cap shadow stayed behind');
  assert.ok(result.finalClamp[0]>result.finalClamp[2]+40,'Local coordinates clipped before assembly scale');
 }finally{await browser.close()}
})().catch(e=>{console.error(e);process.exitCode=1});
