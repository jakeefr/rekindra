const {chromium}=require(process.env.REKINDRA_PLAYWRIGHT_PATH||'playwright');
const fs=require('fs'),path=require('path'),assert=require('node:assert/strict');
(async()=>{
 const fixture=JSON.parse(fs.readFileSync(process.argv[2],'utf8')),out=path.resolve(process.argv[3]);fs.mkdirSync(out,{recursive:true});
 const browser=await chromium.launchPersistentContext(path.join(out,'profile'),{channel:'chrome',headless:true});
 try{const page=await browser.newPage();await page.setContent('');await page.addScriptTag({path:path.resolve('runtime/world.js')});
  const results=await page.evaluate(({scene,programs})=>{
   const renderer=RekindraWorld.createRenderer(scene,programs),canvas=document.createElement('canvas');canvas.width=scene.width;canvas.height=scene.height;const ctx=canvas.getContext('2d');
   const capture=(r,t)=>{ctx.drawImage(r.render(t),0,0);return canvas.toDataURL().split(',')[1]};
   const rows=[];
   for(const [time,index]of [[0,0],[2.0129,0],[2.013,1],[2.02,1],[3.9999,1],[4,2],[6,2]]){
    const key=scene.camera[index],fixed={...scene,camera:[{...key,at:0,cut:false},{...key,at:scene.duration,cut:false}]};
    const control=RekindraWorld.createRenderer(fixed,programs),png=capture(renderer,time),expected=capture(control,time),initial=capture(control,0);control.dispose();
    rows.push({time,index,equal:png===expected,globalTimeVisible:time===0||png!==initial,png});
   }
   const initial=capture(renderer,0);capture(renderer,4);const repeat=initial===capture(renderer,0);renderer.dispose();
   const start={at:0,eye:[0,3,4],target:[0,0,0],fov:50},cut={at:23/30,eye:[3,4,0],target:[0,0,0],fov:30,cut:true};
   const boundaryScene={...scene,camera:[start,cut,{...cut,at:6,cut:false}]};
   const boundary=RekindraWorld.createRenderer(boundaryScene,programs);
   for(const [time,key]of [[0.7666666666666666,start],[23/30,cut],[0.7666666666666668,cut]]){
    const control=RekindraWorld.createRenderer({...scene,camera:[{...key,at:0,cut:false},{...key,at:6,cut:false}]},programs);
    const png=capture(boundary,time),expected=capture(control,time),initial=capture(control,0);control.dispose();
    rows.push({time,index:'rounding-boundary',equal:png===expected,globalTimeVisible:png!==initial,png});
   }boundary.dispose();return{rows,repeat};
  },fixture);
  for(const row of results.rows){fs.writeFileSync(path.join(out,`t-${row.time}.png`),Buffer.from(row.png,'base64'));delete row.png}
  fs.writeFileSync(path.join(out,'result.json'),JSON.stringify(results,null,2));console.log(JSON.stringify(results));
  assert.equal(results.repeat,true);for(const r of results.rows){assert.equal(r.equal,true,`Wrong shot at ${r.time}`);assert.equal(r.globalTimeVisible,true,`Object time reset at ${r.time}`)}
 }finally{await browser.close()}
})().catch(e=>{console.error(e);process.exitCode=1});
