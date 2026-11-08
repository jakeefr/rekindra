// Glow surfaces add light: never darken, cast no shadow, stay hidden behind opaque matter, fade at silhouettes.
const {chromium}=require(process.env.REKINDRA_PLAYWRIGHT_PATH||'playwright');
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
(async()=>{
 const out=path.resolve(process.env.REKINDRA_BROWSER_OUTPUT||'.local/glow');fs.mkdirSync(out,{recursive:true});
 const browser=await chromium.launchPersistentContext(path.join(out,'profile'),{channel:'chrome',headless:true});
 try{
  const page=await browser.newPage();await page.setContent('');await page.addScriptTag({path:path.resolve('runtime/world.js')});
  const r=await page.evaluate(()=>{
   const W=640,H=360,camera={at:0,eye:[0,4,10],target:[0,1.5,0],fov:50};
   const env={sky_top:'#202838',sky_bottom:'#404858',fog_color:'#000000',fog_density:0,light_color:'#FFFFFF',light_direction:[1,1,.3],sun_size:.05,sun_strength:2,fill_strength:.2,ambient_strength:.2};
   const ground={id:'ground',segments:[4,4],color:'#909090',color_high:'#909090',roughness:1,metalness:0,emission:0};
   const tube={id:'tube',segments:[48,8],color:'#FFC060',color_high:'#FFC060',roughness:1,metalness:0,emission:0};
   const wall={id:'wall',segments:[2,2],color:'#305070',color_high:'#305070',roughness:1,metalness:0,emission:0};
   const P={ground:{position:['(u-.5)*30.','0.','(v-.5)*30.'],color_mix:'0.'},tube:{position:['cos(u*2.*pi)','.5+v*2.5','sin(u*2.*pi)'],color_mix:'0.'},wall:{position:['-2.5+u*2.4','v*4.','2.5'],color_mix:'0.'},ghost:{position:['cos(u*2.*pi)','v','40.+sin(u*2.*pi)'],color_mix:'0.'}};
   // Any glow surface switches the renderer off MSAA, so every control carries one behind the camera: compare like with like.
   const ghost={...tube,id:'ghost',glow:1};
   function capture(objs){
    const scene={width:W,height:H,camera:[camera,{...camera,at:12}],environment:env,objects:objs};
    const rr=RekindraWorld.createRenderer(scene,objs.map(o=>P[o.id])),c=document.createElement('canvas');c.width=W;c.height=H;
    const x=c.getContext('2d');x.drawImage(rr.render(0),0,0);rr.dispose();
    return{px:Array.from(x.getImageData(0,0,W,H).data),png:c.toDataURL().split(',')[1]};
   }
   const proj=p=>RekindraWorld.projectPoint(p,camera,W,H).map(Math.round);
   const mirror={...ground,position:{y:'0'},reflection:{strength:.8,blur:0}};
   return{W,none:capture([ground,wall,ghost]),glow:capture([ground,{...tube,glow:1},wall]),opaque:capture([ground,tube,wall,ghost]),
    bare:capture([ground,ghost]),bareGlow:capture([ground,{...tube,glow:1}]),
    mirror:capture([mirror,ghost]),mirrorGlow:capture([mirror,{...tube,glow:1}]),
    pts:{behindWall:proj([-.6,1.75,.8]),centre:proj([0,1.75,1]),edge:proj([.95,1.75,.31]),reflected:proj([0,-1.75,1])}};
  });
  for(const k of ['none','glow','opaque','bareGlow','mirrorGlow'])fs.writeFileSync(path.join(out,k+'.png'),Buffer.from(r[k].png,'base64'));
  const lum=(img,i)=>img.px[i]+img.px[i+1]+img.px[i+2];
  const at=([x,y])=>(y*r.W+x)*4;
  let darker=0,brighter=0,shadowed=0;
  for(let i=0;i<r.none.px.length;i+=4){
   if(lum(r.glow,i)<lum(r.none,i)-3)darker++;
   if(lum(r.glow,i)>lum(r.none,i)+30)brighter++;
   if(lum(r.opaque,i)<lum(r.none,i)-30)shadowed++;
  }
  let mirrorDarker=0;for(let i=0;i<r.mirror.px.length;i+=4)if(lum(r.mirrorGlow,i)<lum(r.mirror,i)-3)mirrorDarker++;
  const d=(p,a=r.glow,b=r.none)=>lum(a,at(p))-lum(b,at(p));
  const metrics={darker,brighter,shadowed,behindWall:d(r.pts.behindWall),behindWallControl:d(r.pts.behindWall,r.bareGlow,r.bare),
   centre:d(r.pts.centre),edge:d(r.pts.edge),reflected:d(r.pts.reflected,r.mirrorGlow,r.mirror),reflectedControl:d(r.pts.reflected,r.bareGlow,r.bare),mirrorDarker};
  fs.writeFileSync(path.join(out,'result.json'),JSON.stringify(metrics,null,2));console.log(metrics);
  assert.ok(shadowed>500,'Control: the opaque tube must visibly shadow or cover the scene');
  assert.equal(darker,0,'Glow must never darken any pixel (additive, no shadow)');
  assert.ok(brighter>500,'Glow must visibly add light');
  assert.ok(metrics.behindWallControl>30,'Control: without the wall this pixel must show the glow');
  assert.ok(Math.abs(metrics.behindWall)<=3,'Opaque wall in front must hide the glow');
  assert.ok(metrics.reflected>20,'A planar reflector must show the glow mirrored below the plane');
  assert.ok(Math.abs(metrics.reflectedControl)<=3,'Control: without the reflector that pixel must not brighten');
  assert.equal(metrics.mirrorDarker,0,'Glow must not darken a reflective scene');
  assert.ok(metrics.centre>metrics.edge+20,'Glow must be brighter facing the camera than at its silhouette');
 }finally{await browser.close()}
})().catch(e=>{console.error(e);process.exitCode=1});
