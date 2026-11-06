(function(root){
  'use strict';
  const sub=(a,b)=>a.map((x,i)=>x-b[i]),dot=(a,b)=>a.reduce((s,x,i)=>s+x*b[i],0);
  const cross=(a,b)=>[a[1]*b[2]-a[2]*b[1],a[2]*b[0]-a[0]*b[2],a[0]*b[1]-a[1]*b[0]];
  const unit=a=>{const n=Math.hypot(...a);if(n<1e-8)throw Error('Degenerate world camera');return a.map(x=>x/n)};
  function cameraAt(keys,t){
    if(t<=keys[0].at)return keys[0];
    for(let i=1;i<keys.length;i++)if(t<=keys[i].at){
      if(keys[i].cut)return t<keys[i].at?{...keys[i-1],at:t}:keys[i];
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
  function cutBetween(keys,from,to){
    let found=null;for(const key of keys)if(key.cut&&key.at>from&&key.at<=to)found=key;
    return found;
  }
  function cameraFrame(keys,t){
    let table=cameraTables.get(keys);
    if(!table){table=[basis(keys[0])];const frames=Math.ceil(keys[keys.length-1].at*30);
      for(let i=1;i<=frames;i++){
        const c=cameraAt(keys,i/30),cut=cutBetween(keys,(i-1)/30,i/30);
        table.push(transport(cut?basis(cut):table[i-1],unit(sub(c.target,c.eye))));
      }cameraTables.set(keys,table)}
    const camera=cameraAt(keys,t);let index=Math.max(0,Math.min(table.length-1,Math.floor(t*30)));
    // Multiplication can round a time just before n/30 up to n. Never borrow
    // an orientation from the future, especially across a discontinuous cut.
    if(index>0&&index/30>t)index--;
    const cut=cutBetween(keys,index/30,t);
    return {camera,basis:transport(cut?basis(cut):table[index],unit(sub(camera.target,camera.eye)))};
  }
  function projectPoint(p,c,w,h){const b=basis(c),d=sub(p,c.eye),z=dot(d,b.forward),tan=Math.tan(c.fov*Math.PI/360);return [w/2+dot(d,b.right)/z/tan*h/2,h/2-dot(d,b.up)/z/tan*h/2,z]}
  const rgb=hex=>[1,3,5].map(i=>Math.pow(parseInt(hex.slice(i,i+2),16)/255,2.2));
  function surfaceMesh(segments,caps=[]){
    const [cols,rows]=segments,vertices=[],indices=[];
    for(let r=0;r<=rows;r++)for(let c=0;c<=cols;c++)vertices.push(c/cols,r/rows,0);
    for(let r=0;r<rows;r++)for(let c=0;c<cols;c++){const a=r*(cols+1)+c,b=a+cols+1;indices.push(a,b,a+1,a+1,b,b+1)}
    for(const cap of caps){
      const start=vertices.length/3,v=cap==='v0'?0:1;
      vertices.push(0,v,1); // center: boundary average evaluated at render time
      for(let c=0;c<=cols;c++)vertices.push(c/cols,v,2);
      for(let c=0;c<cols;c++)indices.push(start,start+1+c,start+2+c);
    }
    return {vertices,indices};
  }
  function shadowFrame(scene){
    const center=scene.camera[0].target.slice(),direction=unit(scene.environment.light_direction);
    const extent=Math.min(160,Math.max(12,...scene.camera.map(c=>Math.hypot(...sub(c.eye,center))*1.2)));
    const b=basis({eye:center.map((v,i)=>v+direction[i]),target:center});
    // Position expressions clamp each world axis to +/-100. Include every legal
    // caster along the light ray, even if it is far outside the camera view.
    const depthExtent=101*b.forward.reduce((s,v)=>s+Math.abs(v),0)+Math.abs(dot(center,b.forward));
    return {center,right:b.right,up:b.up,forward:b.forward,extent,depthExtent};
  }
  const math=`
float bound(float a){return clamp(a,-10000.,10000.);}
float rdiv(float a,float b){return bound(a/(abs(b)<.0001?(b<0.?-.0001:.0001):b));}
float rsqrt(float a){return sqrt(max(0.,a));}
float rexp(float a){return exp(clamp(a,-16.,16.));}
float rpow(float a,float b){return bound(pow(clamp(a,.0001,10000.),clamp(b,-8.,8.)));}
float rclamp(float a,float b,float c){return clamp(a,min(b,c),max(b,c));}
float rmix(float a,float b,float c){return mix(a,b,clamp(c,0.,1.));}
const float pi=3.141592653589793;`;
  const uniforms=`uniform vec3 eye,forward,right,up,skyTop,skyBottom,fogColor,lightColor,lightDir,fillColor,fillDir;
uniform float tanHalf,aspect,fogDensity,sunSize,sunStrength,fillStrength,exposure,t;`;
  const shadowUniforms=`uniform vec3 shadowCenter,shadowRight,shadowUp,shadowForward;uniform float shadowExtent,shadowDepthExtent;
vec3 shadowPoint(vec3 p){vec3 d=p-shadowCenter;return vec3(dot(d,shadowRight)/shadowExtent,dot(d,shadowUp)/shadowExtent,dot(d,shadowForward)/shadowDepthExtent);}`;
  const sky=`
vec3 atmosphere(vec3 ray){
 float height=clamp(ray.y*.9+.12,0.,1.);
 vec3 col=mix(skyBottom,skyTop,pow(height,.55));
 float sun=max(0.,dot(normalize(ray),lightDir));
 float disc=smoothstep(cos(sunSize*1.08),cos(sunSize*.92),sun);
 col+=lightColor*(disc*sunStrength*2.5+pow(sun,120.)*sunStrength*.18);
 return col;
}
vec3 displayColor(vec3 c){return pow(vec3(1.)-exp(-max(c,vec3(0.))*exposure),vec3(1./2.2));}`;
  function createRenderer(scene,programs){
    const reflector=scene.objects.find(o=>(o.reflection?.strength??0)>0);
    const reflectionHeight=reflector?Number(reflector.position.y):0;
    const reflectionUniforms=reflector?'uniform float reflectionPass,reflectionHeight,reflectionActive;':'';
    const reflectionClip=reflector?'if(reflectionPass>.5&&worldPos.y<reflectionHeight-.001)discard;':'';
    const contactEnabled=(scene.environment.occlusion_strength??0)>0;
    const contactShader=contactEnabled?`
uniform highp sampler2D cameraDepth;uniform float occlusionStrength,occlusionRadius;
float indirectVisibility(vec3 P,vec3 N){
 vec3 axis=abs(N.y)<.9?vec3(0.,1.,0.):vec3(1.,0.,0.);
 vec3 T=normalize(cross(axis,N)),B=cross(N,T);float obscured=0.;
 for(int i=0;i<16;i++){
  float f=(float(i)+.5)/16.,angle=float(i)*2.39996323;
  vec3 direction=T*cos(angle)*sqrt(f)+B*sin(angle)*sqrt(f)+N*sqrt(1.-f);
  vec3 Q=P+direction*occlusionRadius*(.25+.75*f),d=Q-eye;float z=dot(d,forward);
  if(z<=.1)continue;
  vec2 uv=vec2(dot(d,right)/(z*tanHalf*aspect),dot(d,up)/(z*tanHalf))*.5+.5;
  if(any(lessThanEqual(uv,vec2(0.)))||any(greaterThanEqual(uv,vec2(1.))))continue;
  float depth=texture(cameraDepth,uv).r;if(depth>=1.)continue;
  float actualZ=${DEPTH_B}/(${DEPTH_A}-(depth*2.-1.));
  if(actualZ>=z-.015*occlusionRadius)continue;
  vec3 actual=eye+forward*actualZ+right*((uv.x*2.-1.)*tanHalf*aspect*actualZ)+up*((uv.y*2.-1.)*tanHalf*actualZ);
  vec3 delta=actual-P;float distance=length(delta);
  if(distance<.02*occlusionRadius)continue;
  float horizon=max(dot(N,delta)/distance-.02,0.);
  obscured+=horizon*(1.-smoothstep(occlusionRadius*.5,occlusionRadius*1.5,distance));
 }
 return 1.-occlusionStrength*clamp(obscured/8.,0.,.85);
}`:'';
    const pointLights=scene.environment.point_lights??[];
    // Distant studio/window radiance. Original bounded lobe approximation:
    // tangent-space rectangles broaden with roughness while their peak drops.
    // Diffuse uses a center-direction solid-angle approximation, not ray tracing.
    const panels=(scene.environment.environment_panels??[]).filter(p=>p.intensity>0);
    const panelUniforms=panels.map((_,i)=>`uniform vec3 panelDirection${i},panelRight${i},panelUp${i},panelColor${i},panelShape${i};`).join('\n');
    const panelShader=panels.length?`
vec3 panelLight(vec3 N,vec3 V,vec3 albedo,float roughness,float metalness,vec3 F,
                vec3 D,vec3 T,vec3 B,vec3 radiance,vec3 shape){
 vec3 R=reflect(-V,N);float facing=dot(R,D),blur=roughness*roughness*.7;
 vec2 width=sqrt(shape.xy*shape.xy+vec2(blur*blur));
 vec2 uv=vec2(dot(R,T),dot(R,B))/max(facing,.0001)/width;
 vec2 square=uv*uv;
 float lobe=facing>0.?exp(-2.*dot(square,square)):0.;
 float compensation=shape.x*shape.y/(width.x*width.y);
 float solidAngle=4.*atan(shape.x*shape.y/sqrt(1.+dot(shape.xy,shape.xy)));
 vec3 diffuse=albedo*(1.-metalness)*(1.-F)*max(dot(N,D),0.)*solidAngle/3.14159265;
 return radiance*shape.z*(diffuse+F*lobe*compensation);
}`:'';
    const panelContribution=panels.map((_,i)=>`panelLight(N,V,albedo,roughness,metalness,envF,panelDirection${i},panelRight${i},panelUp${i},panelColor${i},panelShape${i})`).join('+');
    const pointUniforms=pointLights.map((_,i)=>`uniform vec3 pointPosition${i},pointColor${i};uniform float pointIntensity${i},pointRange${i};`).join('\n');
    const pointBRDF=pointLights.length?`
vec3 localBRDF(vec3 N,vec3 V,vec3 L,vec3 albedo,float roughness,float metalness){
 float nl=max(dot(N,L),0.),nv=max(dot(N,V),.001);
 vec3 hv=V+L,H=length(hv)>.00001?normalize(hv):N;
 float nh=max(dot(N,H),0.),vh=max(dot(V,H),0.);
 float a=max(.06,roughness*roughness),a2=a*a,d=nh*nh*(a2-1.)+1.;
 float distribution=a2/(3.14159265*d*d);
 float gv=2.*nv/(nv+sqrt(a2+(1.-a2)*nv*nv));
 float gl=2.*nl/max(nl+sqrt(a2+(1.-a2)*nl*nl),.00001);
 vec3 f0=mix(vec3(.04),albedo,metalness),f=f0+(1.-f0)*pow(1.-vh,5.);
 return ((1.-f)*(1.-metalness)*albedo/3.14159265+distribution*gv*gl*f/max(4.*nv*nl,.0001))*nl;
}`:'';
    const pointContribution=pointLights.map((_,i)=>`{
 vec3 delta=pointPosition${i}-worldPos;float distance2=dot(delta,delta);
 vec3 L=delta*inversesqrt(max(distance2,.000001));
 float q=distance2/(pointRange${i}*pointRange${i});float fade=max(1.-q*q,0.);
 lit+=localBRDF(N,V,L,albedo,roughness,metalness)*pointColor${i}*pointIntensity${i}*fade*fade/max(distance2,.25);
}`).join('\n');
    const controlledAmbient=(scene.environment.ambient_strength??1)!==1||(scene.environment.ground_strength??0)>0;
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
    function setup(p,c,b,time,pass=0){gl.useProgram(p.p);const e=scene.environment,keyDirection=unit(e.light_direction);
      if(reflector){uniform(p,'reflectionPass',pass);uniform(p,'reflectionHeight',reflectionHeight);uniform(p,'reflectionActive',c.eye[1]>reflectionHeight+.001?1:0);gl.uniform1i(gl.getUniformLocation(p.p,'reflectionImage'),2);}
      const values={eye:c.eye,forward:b.forward,right:b.right,up:b.up,tanHalf:Math.tan(c.fov*Math.PI/360),aspect:scene.width/scene.height,
        skyTop:rgb(e.sky_top),skyBottom:rgb(e.sky_bottom),fogColor:rgb(e.fog_color),lightColor:rgb(e.light_color),lightDir:keyDirection,
        fogDensity:e.fog_density,sunSize:e.sun_size,sunStrength:e.sun_strength,t:time,
        fillColor:rgb(e.fill_color??'#B8D1FF'),fillDir:unit(e.fill_direction??[-keyDirection[0],.5,-keyDirection[2]]),
        fillStrength:e.fill_strength??.25,exposure:e.exposure??1,
        ambientStrength:e.ambient_strength??1,groundStrength:e.ground_strength??0,groundColor:rgb(e.ground_color??'#342A20')};
      if(contactEnabled){values.occlusionStrength=e.occlusion_strength;values.occlusionRadius=e.occlusion_radius??1;gl.uniform1i(gl.getUniformLocation(p.p,'cameraDepth'),1);}
      for(const [name,value] of Object.entries(values))uniform(p,name,value);
      pointLights.forEach((light,i)=>{uniform(p,'pointPosition'+i,light.position);uniform(p,'pointColor'+i,rgb(light.color));uniform(p,'pointIntensity'+i,light.intensity);uniform(p,'pointRange'+i,light.range)});
      panels.forEach((panel,i)=>{
        const d=unit(panel.direction),a=unit(cross(Math.abs(d[1])>.99?[0,0,1]:[0,1,0],d)),b=cross(d,a);
        const c=Math.cos(panel.rotation),s=Math.sin(panel.rotation);
        uniform(p,'panelDirection'+i,d);uniform(p,'panelRight'+i,a.map((x,j)=>x*c+b[j]*s));
        uniform(p,'panelUp'+i,b.map((x,j)=>x*c-a[j]*s));uniform(p,'panelColor'+i,rgb(panel.color));
        uniform(p,'panelShape'+i,[...panel.size,panel.intensity]);
      });
      uniform(p,'shadowCenter',shadow.center);uniform(p,'shadowRight',shadow.right);uniform(p,'shadowUp',shadow.up);
      uniform(p,'shadowForward',shadow.forward);uniform(p,'shadowExtent',shadow.extent);
      uniform(p,'shadowDepthExtent',shadow.depthExtent);
    }
    const shadow=shadowFrame(scene),shadowSize=2048;
    const depthTexture=gl.createTexture(),shadowBuffer=gl.createFramebuffer();
    gl.bindTexture(gl.TEXTURE_2D,depthTexture);
    gl.texImage2D(gl.TEXTURE_2D,0,gl.DEPTH_COMPONENT24,shadowSize,shadowSize,0,gl.DEPTH_COMPONENT,gl.UNSIGNED_INT,null);
    gl.texParameteri(gl.TEXTURE_2D,gl.TEXTURE_MIN_FILTER,gl.NEAREST);gl.texParameteri(gl.TEXTURE_2D,gl.TEXTURE_MAG_FILTER,gl.NEAREST);
    gl.texParameteri(gl.TEXTURE_2D,gl.TEXTURE_WRAP_S,gl.CLAMP_TO_EDGE);gl.texParameteri(gl.TEXTURE_2D,gl.TEXTURE_WRAP_T,gl.CLAMP_TO_EDGE);
    gl.bindFramebuffer(gl.FRAMEBUFFER,shadowBuffer);gl.framebufferTexture2D(gl.FRAMEBUFFER,gl.DEPTH_ATTACHMENT,gl.TEXTURE_2D,depthTexture,0);
    gl.drawBuffers([gl.NONE]);gl.readBuffer(gl.NONE);
    if(gl.checkFramebufferStatus(gl.FRAMEBUFFER)!==gl.FRAMEBUFFER_COMPLETE)throw Error('World shadow buffer unavailable');
    gl.bindFramebuffer(gl.FRAMEBUFFER,null);gl.bindTexture(gl.TEXTURE_2D,null);
    let cameraDepthTexture=null,cameraDepthBuffer=null;
    if(contactEnabled){
      cameraDepthTexture=gl.createTexture();cameraDepthBuffer=gl.createFramebuffer();gl.bindTexture(gl.TEXTURE_2D,cameraDepthTexture);
      gl.texImage2D(gl.TEXTURE_2D,0,gl.DEPTH_COMPONENT24,canvas.width,canvas.height,0,gl.DEPTH_COMPONENT,gl.UNSIGNED_INT,null);
      gl.texParameteri(gl.TEXTURE_2D,gl.TEXTURE_MIN_FILTER,gl.NEAREST);gl.texParameteri(gl.TEXTURE_2D,gl.TEXTURE_MAG_FILTER,gl.NEAREST);
      gl.texParameteri(gl.TEXTURE_2D,gl.TEXTURE_WRAP_S,gl.CLAMP_TO_EDGE);gl.texParameteri(gl.TEXTURE_2D,gl.TEXTURE_WRAP_T,gl.CLAMP_TO_EDGE);
      gl.bindFramebuffer(gl.FRAMEBUFFER,cameraDepthBuffer);gl.framebufferTexture2D(gl.FRAMEBUFFER,gl.DEPTH_ATTACHMENT,gl.TEXTURE_2D,cameraDepthTexture,0);
      gl.drawBuffers([gl.NONE]);gl.readBuffer(gl.NONE);
      if(gl.checkFramebufferStatus(gl.FRAMEBUFFER)!==gl.FRAMEBUFFER_COMPLETE)throw Error('World contact depth buffer unavailable');
      gl.bindFramebuffer(gl.FRAMEBUFFER,null);gl.bindTexture(gl.TEXTURE_2D,null);
    }
    let reflectionTexture=null,reflectionBuffer=null,reflectionDepth=null;
    if(reflector){
      reflectionTexture=gl.createTexture();gl.bindTexture(gl.TEXTURE_2D,reflectionTexture);
      gl.texImage2D(gl.TEXTURE_2D,0,gl.RGBA8,canvas.width,canvas.height,0,gl.RGBA,gl.UNSIGNED_BYTE,null);
      gl.texParameteri(gl.TEXTURE_2D,gl.TEXTURE_MIN_FILTER,gl.LINEAR);gl.texParameteri(gl.TEXTURE_2D,gl.TEXTURE_MAG_FILTER,gl.LINEAR);
      gl.texParameteri(gl.TEXTURE_2D,gl.TEXTURE_WRAP_S,gl.CLAMP_TO_EDGE);gl.texParameteri(gl.TEXTURE_2D,gl.TEXTURE_WRAP_T,gl.CLAMP_TO_EDGE);
      reflectionDepth=gl.createRenderbuffer();gl.bindRenderbuffer(gl.RENDERBUFFER,reflectionDepth);
      gl.renderbufferStorage(gl.RENDERBUFFER,gl.DEPTH_COMPONENT24,canvas.width,canvas.height);
      reflectionBuffer=gl.createFramebuffer();gl.bindFramebuffer(gl.FRAMEBUFFER,reflectionBuffer);
      gl.framebufferTexture2D(gl.FRAMEBUFFER,gl.COLOR_ATTACHMENT0,gl.TEXTURE_2D,reflectionTexture,0);
      gl.framebufferRenderbuffer(gl.FRAMEBUFFER,gl.DEPTH_ATTACHMENT,gl.RENDERBUFFER,reflectionDepth);
      if(gl.checkFramebufferStatus(gl.FRAMEBUFFER)!==gl.FRAMEBUFFER_COMPLETE)throw Error('World reflection buffer unavailable');
      gl.bindFramebuffer(gl.FRAMEBUFFER,null);gl.bindRenderbuffer(gl.RENDERBUFFER,null);gl.bindTexture(gl.TEXTURE_2D,null);
    }
    const skyProgram=program(`#version 300 es
precision highp float;out vec2 screen;void main(){vec2 p=vec2((gl_VertexID<<1)&2,gl_VertexID&2);screen=p*2.-1.;gl_Position=vec4(screen,0.,1.);}`,
      `#version 300 es
precision highp float;in vec2 screen;out vec4 pixel;${uniforms}${sky}
void main(){vec3 ray=normalize(forward+right*screen.x*tanHalf*aspect+up*screen.y*tanHalf);pixel=vec4(displayColor(atmosphere(ray)),1.);}`);
    const surfaces=scene.objects.map((o,index)=>{
      const source=programs[index],isReflector=o===reflector;
      const reflectionShader=isReflector?`
uniform highp sampler2D reflectionImage;
vec3 reflectedRadiance(){
 vec2 extent=vec2(${scene.width}.,${scene.height}.),uv=gl_FragCoord.xy/extent;
 vec3 encoded=vec3(0.);
 ${o.reflection.blur>0?`for(int y=-1;y<=1;y++)for(int x=-1;x<=1;x++)encoded+=texture(reflectionImage,uv+vec2(float(x),float(y))*${Number(o.reflection.blur).toFixed(8)}/extent).rgb/9.;`:'encoded=texture(reflectionImage,uv).rgb;'}
 return -log(max(vec3(1.)-pow(encoded,vec3(2.2)),vec3(.000001)))/exposure;
}`:'';
      const hasColorDetail=source.color_detail!==undefined,hasBump=source.bump_detail!==undefined;
      const hasColorPattern=source.color_pattern!==undefined;
      const hasDetail=hasColorDetail||hasBump||hasColorPattern;
      const hasCaps=Boolean(o.caps?.length);
      const hasInstances=o.instances!==undefined;
      const hasInstanceRotation=o.instances?.some(p=>p.rotation!==undefined)??false;
      const definitions=source.definitions??'';
      let position=hasInstances?`uniform vec3 instanceOffset,instanceScale;
vec3 surface(float u,float v){${definitions}vec3 local=clamp(vec3(${source.position.join(',')}),vec3(-100.),vec3(100.));return clamp(local*instanceScale+instanceOffset,vec3(-100.),vec3(100.));}`:
        `vec3 surface(float u,float v){${definitions}return clamp(vec3(${source.position.join(',')}),vec3(-100.),vec3(100.));}`;
      if(source.assembly!==undefined||hasInstanceRotation){
        position=`${hasInstances?'uniform vec3 instanceOffset,instanceScale;':''}${hasInstanceRotation?'uniform vec3 instanceRotation;':''}
vec3 surface(float u,float v){${definitions}vec3 p=vec3(${source.position.join(',')});
${hasInstances?'p*=instanceScale;':''}
${hasInstanceRotation?`vec3 c=cos(instanceRotation),s=sin(instanceRotation);
p=vec3(p.x,c.x*p.y-s.x*p.z,s.x*p.y+c.x*p.z);
p=vec3(c.y*p.x+s.y*p.z,p.y,-s.y*p.x+c.y*p.z);
p=vec3(c.z*p.x-s.z*p.y,s.z*p.x+c.z*p.y,p.z);`:''}
${hasInstances?'p+=instanceOffset;':''}${source.assembly??''}return clamp(p,vec3(-100.),vec3(100.));}`;
      }
      const capPosition=hasCaps?`vec3 point(vec3 uv){if(uv.z>.5&&uv.z<1.5){vec3 center=vec3(0.);for(int i=0;i<${o.segments[0]};i++)center+=surface(float(i)/${o.segments[0]}.,uv.y);return center/${o.segments[0]}.;}return surface(uv.x,uv.y);}`:'';
      const p=program(`#version 300 es
precision highp float;layout(location=0)in vec3 uv;out vec3 worldPos,worldNormal;out float blend;${hasDetail?'out vec2 detailUV;':''}${hasCaps?'flat out float capFace;':''}
${uniforms}${math}${position}${capPosition}
void main(){float u=uv.x,v=uv.y;${hasDetail?'detailUV=uv.xy;':''}${hasCaps?'capFace=uv.z>.5?1.:0.;':''}${definitions}vec3 pos=${hasCaps?'point(uv)':'surface(u,v)'};
vec3 du=surface(u+.0005,v)-surface(u-.0005,v),dv=surface(u,v+.0005)-surface(u,v-.0005);
vec3 n=cross(dv,du);worldNormal=length(n)>.0000001?normalize(n):vec3(0.,1.,0.);
worldPos=pos;blend=clamp(${source.color_mix},0.,1.);vec3 d=pos-eye;float z=dot(d,forward);
gl_Position=vec4(dot(d,right)/(tanHalf*aspect),dot(d,up)/tanHalf,${DEPTH_A}*z-${DEPTH_B},z);}`,
        `#version 300 es
precision highp float;in vec3 worldPos,worldNormal;in float blend;out vec4 pixel;${hasDetail?'in vec2 detailUV;'+math:''}${hasCaps?'flat in float capFace;':''}
${uniforms}${reflectionUniforms}${reflectionShader}${shadowUniforms}uniform highp sampler2D shadowDepth;
uniform vec3 baseColor,highColor;uniform float roughness,metalness,emission;
${controlledAmbient?'uniform vec3 groundColor;uniform float ambientStrength,groundStrength;':''}${sky}${pointUniforms}${pointBRDF}${contactShader}${panelUniforms}${panelShader}
float visibility(vec3 p,float nl){
 vec3 q=shadowPoint(p)*.5+.5;
 // Neighboring texels lie at different depths on a sloped receiver. Compare
 // each tap against that plane, not against the center pixel's depth.
 // Derivatives must be evaluated before any nonuniform coverage branch.
 vec3 qx=dFdx(q),qy=dFdy(q);float det=qx.x*qy.y-qx.y*qy.x;
 vec2 gradient=abs(det)>1.e-12?vec2(qx.z*qy.y-qx.y*qy.z,qx.x*qy.z-qx.z*qy.x)/det:vec2(0.);
 gradient=clamp(gradient,vec2(-4.),vec2(4.));
 if(any(lessThanEqual(q,vec3(0.)))||any(greaterThanEqual(q,vec3(1.))))return 1.;
 float slope=sqrt(max(0.,1.-nl*nl))/max(nl,.1);
 float bias=(.003+min(.06,.75*(2.*shadowExtent/2048.)*slope))/(2.*shadowDepthExtent),sum=0.,blockerGap=0.,blockers=0.;
 // Bounded blocker search estimates a penumbra from source angular radius.
 float searchRadius=clamp(tan(sunSize)*.06,1./2048.,10./2048.);
 for(int i=0;i<16;i++){
  float angle=float(i)*2.39996323,r=sqrt((float(i)+.5)/16.);
  vec2 tap=(floor((q.xy+vec2(cos(angle),sin(angle))*r*searchRadius)*2048.)+.5)/2048.;
  if(any(lessThan(tap,vec2(0.)))||any(greaterThan(tap,vec2(1.))))continue;
  float depth=texture(shadowDepth,tap).r,receiver=q.z+dot(gradient,tap-q.xy);
  if(depth<receiver-bias){blockerGap+=receiver-depth;blockers+=1.;}
 }
 float radius=1.;
 if(blockers>0.)radius=clamp((blockerGap/blockers)*shadowDepthExtent*tan(sunSize)/shadowExtent*2048.,1.,12.);
 for(int i=0;i<32;i++){
  float angle=float(i)*2.39996323,r=sqrt((float(i)+.5)/32.);
  vec2 tap=(floor(q.xy*2048.+vec2(cos(angle),sin(angle))*r*radius)+.5)/2048.;
  if(any(lessThan(tap,vec2(0.)))||any(greaterThan(tap,vec2(1.)))){sum+=1.;continue;}
  float depth=texture(shadowDepth,tap).r,receiver=q.z+dot(gradient,tap-q.xy);
  sum+=receiver-bias<=depth?1.:0.;
 }return sum/32.;
}
void main(){vec3 V=normalize(eye-worldPos),N=normalize(worldNormal);
${o.shading==='flat'?'vec3 faceNormal=cross(dFdx(worldPos),dFdy(worldPos));if(length(faceNormal)>1.e-10)N=normalize(faceNormal);':hasCaps?'vec3 faceNormal=cross(dFdx(worldPos),dFdy(worldPos));if(capFace>.5&&length(faceNormal)>1.e-10)N=normalize(faceNormal);':''}
// Orient against the visible triangle, not the interpolated normal/view dot.
// The latter can cross zero inside a grazing triangle and flip a whole strip.
vec3 facingFace=cross(dFdx(worldPos),dFdy(worldPos));
// Mirrored camera bases reverse raster handedness; face the geometric normal
// toward this pass's eye before using it to orient the smooth/cap normal.
if(dot(facingFace,V)<0.)facingFace=-facingFace;
if(dot(N,length(facingFace)>1.e-10?facingFace:V)<0.)N=-N;
${hasBump?`float geometricNl=max(dot(N,lightDir),0.);`:''}
${hasColorPattern?`float u=detailUV.x,v=detailUV.y;
float patternBlend=clamp(${source.color_pattern},0.,1.);
vec3 albedo=mix(baseColor,highColor,${hasCaps?'capFace>.5?blend:patternBlend':'patternBlend'});`:
`vec3 albedo=mix(baseColor,highColor,blend);
${hasDetail?'float u=detailUV.x,v=detailUV.y;':''}`}
${hasColorDetail?`float detail=clamp(${source.color_detail},-.35,.35);albedo*=1.+detail${hasCaps?'*(1.-capFace)':''};`:''}
${hasBump?`// Surface-gradient bump mapping in world units, independent of tessellation.
// Evaluate derivatives before branching. Degenerate/grazing pixels retain N.
float height=clamp(${source.bump_detail},-.1,.1);
vec3 dx=dFdx(worldPos),dy=dFdy(worldPos),rx=cross(dy,N),ry=cross(N,dx);
float determinant=dot(dx,rx),hx=dFdx(height),hy=dFdy(height);
vec3 gradient=(hx*rx+hy*ry)/(abs(determinant)>1.e-10?determinant:1.);
if(abs(determinant)>1.e-10${hasCaps?'&&capFace<.5':''}){gradient*=min(1.,.6/max(length(gradient),.00001));N=normalize(N-gradient);}
`:''}
float nl=max(dot(N,lightDir),0.),nv=max(dot(N,V),.001);
vec3 hv=V+lightDir;vec3 H=length(hv)>.00001?normalize(hv):N;
float nh=max(dot(N,H),0.),vh=max(dot(V,H),0.);
float a=max(.06,roughness*roughness),a2=a*a,d=nh*nh*(a2-1.)+1.;
float distribution=a2/(3.14159265*d*d);
float gv=2.*nv/(nv+sqrt(a2+(1.-a2)*nv*nv));
float gl=2.*nl/max(nl+sqrt(a2+(1.-a2)*nl*nl),.00001);
vec3 f0=mix(vec3(.04),albedo,metalness),f=f0+(1.-f0)*pow(1.-vh,5.);
vec3 spec=distribution*gv*gl*f/max(4.*nv*nl,.0001);
vec3 diffuse=(1.-f)*(1.-metalness)*albedo/3.14159265;
vec3 lit=(diffuse+spec)*lightColor*(sunStrength*3.)*nl*visibility(worldPos,${hasBump?'geometricNl':'nl'});
lit+=albedo*(1.-metalness)*fillColor*fillStrength*max(dot(N,fillDir),0.);
${pointContribution}
vec3 hemisphere=mix(skyBottom,skyTop,N.y*.5+.5);
${controlledAmbient?'vec3 diffuseHemisphere=mix(hemisphere,groundColor,(1.-clamp(N.y,-1.,1.))*.5*groundStrength);vec3 ambient=albedo*(1.-metalness)*(.055+diffuseHemisphere*.22)*ambientStrength;':'vec3 ambient=albedo*(1.-metalness)*(.055+hemisphere*.22);'}
vec3 reflected=mix(atmosphere(reflect(-V,N)),hemisphere,roughness*roughness);
vec3 envF=f0+(max(vec3(1.-roughness),f0)-f0)*pow(1.-nv,5.);
${contactEnabled?'float indirect=indirectVisibility(worldPos,N);lit+=(ambient+reflected*envF*(1.-roughness*.45))*indirect+albedo*emission;':'lit+=ambient+reflected*envF*(1.-roughness*.45)+albedo*emission;'}
${panels.length?`lit+=(${panelContribution})${contactEnabled?'*indirect':''};`:''}
float fog=1.-exp(-length(eye-worldPos)*fogDensity);lit=mix(lit,fogColor,fog);
${reflectionClip}
${isReflector?`if(reflectionActive>.5)lit=mix(lit,reflectedRadiance(),${Number(o.reflection.strength).toFixed(8)});`:''}
pixel=vec4(displayColor(lit),1.);}`);
      const depthProgram=program(`#version 300 es
precision highp float;layout(location=0)in vec3 uv;uniform float t;${math}${shadowUniforms}${position}${capPosition}
void main(){gl_Position=vec4(shadowPoint(${hasCaps?'point(uv)':'surface(uv.x,uv.y)'}),1.);}`,
        `#version 300 es
precision highp float;void main(){}`);
      const cameraDepthProgram=contactEnabled?program(`#version 300 es
precision highp float;layout(location=0)in vec3 uv;${reflector?'out vec3 worldPos;':''}${uniforms}${math}${position}${capPosition}
void main(){vec3 pos=${hasCaps?'point(uv)':'surface(uv.x,uv.y)'};${reflector?'worldPos=pos;':''}vec3 d=pos-eye;float z=dot(d,forward);gl_Position=vec4(dot(d,right)/(tanHalf*aspect),dot(d,up)/tanHalf,${DEPTH_A}*z-${DEPTH_B},z);}`,
        `#version 300 es
precision highp float;${reflector?'in vec3 worldPos;'+reflectionUniforms:''}void main(){${reflectionClip}}`):null;
      const {vertices,indices}=surfaceMesh(o.segments,o.caps);
      const vao=gl.createVertexArray();gl.bindVertexArray(vao);
      const vb=gl.createBuffer();gl.bindBuffer(gl.ARRAY_BUFFER,vb);gl.bufferData(gl.ARRAY_BUFFER,new Float32Array(vertices),gl.STATIC_DRAW);gl.enableVertexAttribArray(0);gl.vertexAttribPointer(0,3,gl.FLOAT,false,0,0);
      const ib=gl.createBuffer();gl.bindBuffer(gl.ELEMENT_ARRAY_BUFFER,ib);gl.bufferData(gl.ELEMENT_ARRAY_BUFFER,new Uint16Array(indices),gl.STATIC_DRAW);gl.bindVertexArray(null);
      return {p,depthProgram,cameraDepthProgram,o,vao,vb,ib,count:indices.length,placements:o.instances??[null]};
    });
    function drawSurface(s,p){
      gl.bindVertexArray(s.vao);
      for(const placement of s.placements){
        if(placement){uniform(p,'instanceOffset',placement.offset);uniform(p,'instanceScale',placement.scale);uniform(p,'instanceRotation',placement.rotation??[0,0,0])}
        gl.drawElements(gl.TRIANGLES,s.count,gl.UNSIGNED_SHORT,0);
      }
    }
    function contactPass(c,b,time,pass){
      if(!contactEnabled)return;
      gl.activeTexture(gl.TEXTURE1);gl.bindTexture(gl.TEXTURE_2D,null);gl.bindFramebuffer(gl.FRAMEBUFFER,cameraDepthBuffer);
      gl.viewport(0,0,canvas.width,canvas.height);gl.enable(gl.DEPTH_TEST);gl.disable(gl.CULL_FACE);gl.disable(gl.POLYGON_OFFSET_FILL);gl.clear(gl.DEPTH_BUFFER_BIT);
      for(const s of surfaces){if(pass&&s.o===reflector)continue;setup(s.cameraDepthProgram,c,b,time,pass);drawSurface(s,s.cameraDepthProgram)}
      gl.bindFramebuffer(gl.FRAMEBUFFER,null);gl.bindTexture(gl.TEXTURE_2D,cameraDepthTexture);gl.activeTexture(gl.TEXTURE0);
    }
    function colorPass(c,b,time,pass){
      gl.viewport(0,0,canvas.width,canvas.height);gl.clear(gl.COLOR_BUFFER_BIT|gl.DEPTH_BUFFER_BIT);
      gl.disable(gl.DEPTH_TEST);gl.bindVertexArray(null);setup(skyProgram,c,b,time,pass);gl.drawArrays(gl.TRIANGLES,0,3);
      gl.enable(gl.DEPTH_TEST);gl.disable(gl.CULL_FACE);
      for(const s of surfaces){if(pass&&s.o===reflector)continue;setup(s.p,c,b,time,pass);uniform(s.p,'baseColor',rgb(s.o.color));uniform(s.p,'highColor',rgb(s.o.color_high));
        for(const name of ['roughness','metalness','emission'])uniform(s.p,name,s.o[name]);drawSurface(s,s.p)}
    }
    function render(time){
      if(lost||gl.isContextLost())throw Error('Graphics context lost. Reload the scene before exporting.');
      const frame=cameraFrame(scene.camera,time),c=frame.camera,b=frame.basis;
      if(contactEnabled&&!reflector){
        gl.activeTexture(gl.TEXTURE1);gl.bindTexture(gl.TEXTURE_2D,null);gl.bindFramebuffer(gl.FRAMEBUFFER,cameraDepthBuffer);
        gl.viewport(0,0,canvas.width,canvas.height);gl.enable(gl.DEPTH_TEST);gl.disable(gl.CULL_FACE);gl.disable(gl.POLYGON_OFFSET_FILL);gl.clear(gl.DEPTH_BUFFER_BIT);
        for(const s of surfaces){setup(s.cameraDepthProgram,c,b,time);drawSurface(s,s.cameraDepthProgram)}
        gl.bindFramebuffer(gl.FRAMEBUFFER,null);gl.bindTexture(gl.TEXTURE_2D,cameraDepthTexture);gl.activeTexture(gl.TEXTURE0);
      }
      gl.bindTexture(gl.TEXTURE_2D,null);gl.bindFramebuffer(gl.FRAMEBUFFER,shadowBuffer);
      gl.viewport(0,0,shadowSize,shadowSize);gl.enable(gl.DEPTH_TEST);gl.disable(gl.CULL_FACE);
      gl.enable(gl.POLYGON_OFFSET_FILL);gl.polygonOffset(1,1);gl.clear(gl.DEPTH_BUFFER_BIT);
      for(const s of surfaces){setup(s.depthProgram,c,b,time);drawSurface(s,s.depthProgram)}
      gl.disable(gl.POLYGON_OFFSET_FILL);gl.bindFramebuffer(gl.FRAMEBUFFER,null);
      gl.activeTexture(gl.TEXTURE0);gl.bindTexture(gl.TEXTURE_2D,depthTexture);gl.viewport(0,0,canvas.width,canvas.height);
      if(reflector){
        if(c.eye[1]>reflectionHeight+.001){
          const mirror=p=>[p[0],-p[1],p[2]],mc={...c,eye:[c.eye[0],2*reflectionHeight-c.eye[1],c.eye[2]]};
          const mb={forward:mirror(b.forward),right:mirror(b.right),up:mirror(b.up)};
          gl.activeTexture(gl.TEXTURE2);gl.bindTexture(gl.TEXTURE_2D,null);gl.activeTexture(gl.TEXTURE0);
          contactPass(mc,mb,time,1);gl.bindFramebuffer(gl.FRAMEBUFFER,reflectionBuffer);colorPass(mc,mb,time,1);
          gl.bindFramebuffer(gl.FRAMEBUFFER,null);gl.activeTexture(gl.TEXTURE2);gl.bindTexture(gl.TEXTURE_2D,reflectionTexture);gl.activeTexture(gl.TEXTURE0);
        }
        contactPass(c,b,time,0);
      }
      gl.clear(gl.COLOR_BUFFER_BIT|gl.DEPTH_BUFFER_BIT);gl.disable(gl.DEPTH_TEST);gl.bindVertexArray(null);setup(skyProgram,c,b,time);gl.drawArrays(gl.TRIANGLES,0,3);
      gl.enable(gl.DEPTH_TEST);gl.disable(gl.CULL_FACE);
      for(const s of surfaces){setup(s.p,c,b,time);uniform(s.p,'baseColor',rgb(s.o.color));uniform(s.p,'highColor',rgb(s.o.color_high));
        for(const name of ['roughness','metalness','emission'])uniform(s.p,name,s.o[name]);drawSurface(s,s.p)}
      gl.bindVertexArray(null);if(gl.getError()!==gl.NO_ERROR)throw Error('World rendering failed');return canvas;
    }
    return {render,canvas,dispose(){for(const s of surfaces){gl.deleteVertexArray(s.vao);gl.deleteBuffer(s.vb);gl.deleteBuffer(s.ib)}for(const p of owned)gl.deleteProgram(p);gl.deleteTexture(depthTexture);gl.deleteFramebuffer(shadowBuffer);if(contactEnabled){gl.deleteTexture(cameraDepthTexture);gl.deleteFramebuffer(cameraDepthBuffer)}if(reflector){gl.deleteTexture(reflectionTexture);gl.deleteFramebuffer(reflectionBuffer);gl.deleteRenderbuffer(reflectionDepth)}}};
  }
  const api={cameraAt,basis,projectPoint,cameraFrame,shadowFrame,surfaceMesh,DEPTH_A,DEPTH_B,createRenderer};if(typeof module!=='undefined')module.exports=api;else root.RekindraWorld=api;
})(globalThis);
