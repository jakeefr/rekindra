const {chromium}=require(process.env.REKINDRA_PLAYWRIGHT_PATH||'playwright');
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict'),{pathToFileURL}=require('node:url');
(async()=>{
 const manifest=JSON.parse(fs.readFileSync(process.argv[2],'utf8')),out=path.resolve('.local/inspection-loop/browser');fs.mkdirSync(out,{recursive:true});
 const context=await chromium.launchPersistentContext(path.join(out,'profile'),{channel:'chrome',headless:true});
 try{
  const page=await context.newPage();await page.goto(pathToFileURL(manifest.inspection).href);await page.waitForFunction(()=>rekindra?.ready);
  const result=await page.evaluate(async()=>{
   let error;try{await rekindra.exportVideo({download:false})}catch(e){error=e.message}
   const frames=[1,3,5,7,9,11].map(t=>RekindraWorld.cameraFrame(rekindra.scene.camera,t));
   const png=rekindra.reviewFrames().png;
   return{inspection:rekindra.data.inspection_only,disabled:document.querySelector('#export').disabled,error,frames,png};
  });
  fs.writeFileSync(path.join(out,'reverse.png'),Buffer.from(result.png,'base64'));delete result.png;
  assert.equal(result.inspection,true);assert.equal(result.disabled,true);assert.match(result.error,/Inspection view only/);
  for(const frame of result.frames){assert.deepEqual(frame.camera.eye,manifest.camera.eye);assert.deepEqual(frame.camera.target,manifest.camera.target);assert.ok(frame.basis.up[1]>.8,'Inspection horizon unexpectedly rolled')}
  await page.goto(pathToFileURL(manifest.normal).href);await page.waitForFunction(()=>rekindra?.ready);
  result.normal=await page.evaluate(()=>({disabled:document.querySelector('#export').disabled,inspection:Boolean(rekindra.data.inspection_only)}));
  assert.deepEqual(result.normal,{disabled:false,inspection:false});
  fs.writeFileSync(path.join(out,'result.json'),JSON.stringify(result,null,2));console.log(JSON.stringify({inspectionBlocked:true,staticCamera:true,upright:true,normalExportEnabled:true}));
 }finally{await context.close()}
})().catch(e=>{console.error(e);process.exitCode=1});
