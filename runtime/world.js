(function(root){
  'use strict';
  const sub=(a,b)=>a.map((x,i)=>x-b[i]),dot=(a,b)=>a.reduce((s,x,i)=>s+x*b[i],0);
  const cross=(a,b)=>[a[1]*b[2]-a[2]*b[1],a[2]*b[0]-a[0]*b[2],a[0]*b[1]-a[1]*b[0]];
  const unit=a=>{const n=Math.hypot(...a);if(n<1e-8)throw Error('Degenerate world camera');return a.map(x=>x/n)};
  function cameraAt(keys,t){
    if(t<=keys[0].at)return keys[0];
    for(let i=1;i<keys.length;i++)if(t<=keys[i].at){
      const a=keys[i-1],b=keys[i],q=(t-a.at)/(b.at-a.at),s=q*q*(3-2*q);
      return {at:t,eye:a.eye.map((x,j)=>x+(b.eye[j]-x)*s),target:a.target.map((x,j)=>x+(b.target[j]-x)*s),fov:a.fov+(b.fov-a.fov)*s};
    }
    return keys[keys.length-1];
  }
  function basis(c){const forward=unit(sub(c.target,c.eye)),right=unit(cross(forward,Math.abs(forward[1])>.99?[0,0,1]:[0,1,0]));return {forward,right,up:unit(cross(right,forward))}}
  // Parallel-transport orientation from a fixed sample table, never from the last displayed frame.
  const cameraTables=new WeakMap(),DEPTH_A=(400+.1)/(400-.1),DEPTH_B=2*400*.1/(400-.1);
  function transport(previous,forward){
    const axis=cross(previous.forward,forward),s=Math.hypot(...axis),c=Math.max(-1,Math.min(1,dot(previous.forward,forward)));
    let right=previous.right;
    if(s>1e-9){const n=axis.map(x=>x/s),nr=cross(n,right),d=dot(n,right);right=right.map((x,i)=>x*c+nr[i]*s+n[i]*d*(1-c))}
    else if(c<0)right=right.map(x=>-x);
    right=unit(sub(right,forward.map(x=>x*dot(right,forward))));
    return {forward,right,up:unit(cross(right,forward))};
  }
  function cameraFrame(keys,t){
    let table=cameraTables.get(keys);
    if(!table){table=[basis(keys[0])];const frames=Math.ceil(keys[keys.length-1].at*30);
      for(let i=1;i<=frames;i++){const c=cameraAt(keys,i/30);table.push(transport(table[i-1],unit(sub(c.target,c.eye))))}cameraTables.set(keys,table)}
    const camera=cameraAt(keys,t),index=Math.max(0,Math.min(table.length-1,Math.floor(t*30)));
    return {camera,basis:transport(table[index],unit(sub(camera.target,camera.eye)))};
  }
  function projectPoint(p,c,w,h){const b=basis(c),d=sub(p,c.eye),z=dot(d,b.forward),tan=Math.tan(c.fov*Math.PI/360);return [w/2+dot(d,b.right)/z/tan*h/2,h/2-dot(d,b.up)/z/tan*h/2,z]}
  const rgb=hex=>[1,3,5].map(i=>Math.pow(parseInt(hex.slice(i,i+2),16)/255,2.2));
  const math=`
float bound(float a){return clamp(a,-10000.,10000.);}
float rdiv(float a,float b){return bound(a/(abs(b)<.0001?(b<0.?-.0001:.0001):b));}
float rsqrt(float a){return sqrt(max(0.,a));}
float rexp(float a){return exp(clamp(a,-16.,16.));}
float rpow(float a,float b){return bound(pow(clamp(a,.0001,10000.),clamp(b,-8.,8.)));}
float rclamp(float a,float b,float c){return clamp(a,min(b,c),max(b,c));}
float rmix(float a,float b,float c){return mix(a,b,clamp(c,0.,1.));}
const float pi=3.141592653589793;`;
  const uniforms=`uniform vec3 eye,forward,right,up,skyTop,skyBottom,fogColor,lightColor,lightDir;
uniform float tanHalf,aspect,fogDensity,sunSize,sunStrength,t;`;
  const sky=`
vec3 atmosphere(vec3 ray){
 float height=clamp(ray.y*.9+.12,0.,1.);
 vec3 col=mix(skyBottom,skyTop,pow(height,.55));
 float sun=max(0.,dot(normalize(ray),lightDir));
 float disc=smoothstep(cos(sunSize*1.08),cos(sunSize*.92),sun);
 col+=lightColor*(disc*sunStrength*2.5+pow(sun,120.)*sunStrength*.18);
 return col;
}
vec3 displayColor(vec3 c){return pow(vec3(1.)-exp(-max(c,vec3(0.))),vec3(1./2.2));}`;
  function createRenderer(scene,programs){
    const canvas=document.createElement('canvas');canvas.width=scene.width;canvas.height=scene.height;
    const gl=canvas.getContext('webgl2',{alpha:false,antialias:true,preserveDrawingBuffer:true});
    if(!gl)throw Error('This generated world needs WebGL2. Use a browser with graphics acceleration.');
    const owned=[];let lost=false;
    canvas.addEventListener('webglcontextlost',e=>{e.preventDefault();lost=true});
    function shader(type,source){const s=gl.createShader(type);gl.shaderSource(s,source);gl.compileShader(s);if(!gl.getShaderParameter(s,gl.COMPILE_STATUS)){const message=gl.getShaderInfoLog(s);gl.deleteShader(s);throw Error('World shader compilation failed: '+message.slice(0,350))}return s}
    function program(vertex,fragment){
      const p=gl.createProgram(),v=shader(gl.VERTEX_SHADER,vertex),f=shader(gl.FRAGMENT_SHADER,fragment);
      gl.attachShader(p,v);gl.attachShader(p,f);gl.linkProgram(p);gl.deleteShader(v);gl.deleteShader(f);
      if(!gl.getProgramParameter(p,gl.LINK_STATUS)){gl.deleteProgram(p);throw Error('World shader link failed')}
      owned.push(p);return {p,locations:{}};
    }
    function uniform(p,name,value){const loc=p.locations[name]??(p.locations[name]=gl.getUniformLocation(p.p,name));if(loc===null)return;
      if(Array.isArray(value))gl.uniform3fv(loc,value);else gl.uniform1f(loc,value)}
    function setup(p,c,b,time){gl.useProgram(p.p);const e=scene.environment;
      const values={eye:c.eye,forward:b.forward,right:b.right,up:b.up,tanHalf:Math.tan(c.fov*Math.PI/360),aspect:scene.width/scene.height,
        skyTop:rgb(e.sky_top),skyBottom:rgb(e.sky_bottom),fogColor:rgb(e.fog_color),lightColor:rgb(e.light_color),lightDir:unit(e.light_direction),
        fogDensity:e.fog_density,sunSize:e.sun_size,sunStrength:e.sun_strength,t:time};
      for(const [name,value] of Object.entries(values))uniform(p,name,value);
    }
    const skyProgram=program(`#version 300 es
precision highp float;out vec2 screen;void main(){vec2 p=vec2((gl_VertexID<<1)&2,gl_VertexID&2);screen=p*2.-1.;gl_Position=vec4(screen,0.,1.);}`,
      `#version 300 es
precision highp float;in vec2 screen;out vec4 pixel;${uniforms}${sky}
void main(){vec3 ray=normalize(forward+right*screen.x*tanHalf*aspect+up*screen.y*tanHalf);pixel=vec4(displayColor(atmosphere(ray)),1.);}`);
    const surfaces=scene.objects.map((o,index)=>{
      const source=programs[index];
      const position=`vec3 surface(float u,float v){return clamp(vec3(${source.position.join(',')}),vec3(-100.),vec3(100.));}`;
      const p=program(`#version 300 es
precision highp float;layout(location=0)in vec2 uv;out vec3 worldPos,worldNormal;out float blend;
${uniforms}${math}${position}
void main(){float u=uv.x,v=uv.y;vec3 pos=surface(u,v);
vec3 du=surface(u+.0005,v)-surface(u-.0005,v),dv=surface(u,v+.0005)-surface(u,v-.0005);
vec3 n=cross(dv,du);worldNormal=length(n)>.0000001?normalize(n):vec3(0.,1.,0.);
worldPos=pos;blend=clamp(${source.color_mix},0.,1.);vec3 d=pos-eye;float z=dot(d,forward);
gl_Position=vec4(dot(d,right)/(tanHalf*aspect),dot(d,up)/tanHalf,${DEPTH_A}*z-${DEPTH_B},z);}`,
        `#version 300 es
precision highp float;in vec3 worldPos,worldNormal;in float blend;out vec4 pixel;
${uniforms}uniform vec3 baseColor,highColor;uniform float roughness,metalness,emission;${sky}
void main(){vec3 V=normalize(eye-worldPos),N=normalize(worldNormal);if(dot(N,V)<0.)N=-N;
vec3 albedo=mix(baseColor,highColor,blend);float diffuse=max(dot(N,lightDir),0.);
vec3 H=normalize(V+lightDir);float exponent=mix(180.,5.,roughness);
float spec=pow(max(dot(N,H),0.),exponent)*(1.-roughness)*2.;
float fresnel=.035+.965*pow(1.-max(dot(N,V),0.),5.);
vec3 reflected=atmosphere(reflect(-V,N));
vec3 lit=albedo*(.24+diffuse*.85)+lightColor*spec;
lit=mix(lit,reflected,clamp(metalness*.45+fresnel*(1.-roughness)*.65,0.,.95))+albedo*emission;
float fog=1.-exp(-length(eye-worldPos)*fogDensity);lit=mix(lit,fogColor,fog);
pixel=vec4(displayColor(lit),1.);}`);
      const [cols,rows]=o.segments,vertices=[],indices=[];
      for(let r=0;r<=rows;r++)for(let c=0;c<=cols;c++)vertices.push(c/cols,r/rows);
      for(let r=0;r<rows;r++)for(let c=0;c<cols;c++){const a=r*(cols+1)+c,b=a+cols+1;indices.push(a,b,a+1,a+1,b,b+1)}
      const vao=gl.createVertexArray();gl.bindVertexArray(vao);
      const vb=gl.createBuffer();gl.bindBuffer(gl.ARRAY_BUFFER,vb);gl.bufferData(gl.ARRAY_BUFFER,new Float32Array(vertices),gl.STATIC_DRAW);gl.enableVertexAttribArray(0);gl.vertexAttribPointer(0,2,gl.FLOAT,false,0,0);
      const ib=gl.createBuffer();gl.bindBuffer(gl.ELEMENT_ARRAY_BUFFER,ib);gl.bufferData(gl.ELEMENT_ARRAY_BUFFER,new Uint16Array(indices),gl.STATIC_DRAW);gl.bindVertexArray(null);
      return {p,o,vao,vb,ib,count:indices.length};
    });
    function render(time){
      if(lost||gl.isContextLost())throw Error('Graphics context lost. Reload the scene before exporting.');
      const frame=cameraFrame(scene.camera,time),c=frame.camera,b=frame.basis;gl.viewport(0,0,canvas.width,canvas.height);
      gl.clear(gl.COLOR_BUFFER_BIT|gl.DEPTH_BUFFER_BIT);gl.disable(gl.DEPTH_TEST);gl.bindVertexArray(null);setup(skyProgram,c,b,time);gl.drawArrays(gl.TRIANGLES,0,3);
      gl.enable(gl.DEPTH_TEST);gl.disable(gl.CULL_FACE);
      for(const s of surfaces){setup(s.p,c,b,time);uniform(s.p,'baseColor',rgb(s.o.color));uniform(s.p,'highColor',rgb(s.o.color_high));
        for(const name of ['roughness','metalness','emission'])uniform(s.p,name,s.o[name]);gl.bindVertexArray(s.vao);gl.drawElements(gl.TRIANGLES,s.count,gl.UNSIGNED_SHORT,0)}
      gl.bindVertexArray(null);if(gl.getError()!==gl.NO_ERROR)throw Error('World rendering failed');return canvas;
    }
    return {render,canvas,dispose(){for(const s of surfaces){gl.deleteVertexArray(s.vao);gl.deleteBuffer(s.vb);gl.deleteBuffer(s.ib)}for(const p of owned)gl.deleteProgram(p)}};
  }
  const api={cameraAt,basis,projectPoint,cameraFrame,DEPTH_A,DEPTH_B,createRenderer};if(typeof module!=='undefined')module.exports=api;else root.RekindraWorld=api;
})(globalThis);
