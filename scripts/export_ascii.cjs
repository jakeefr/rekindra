// Development-only native browser video export/decode (not full acceptance).
// Default ASCII in color; --mono exports black-and-white ASCII; --standard exports the normal display for diagnostic review.
// --detail=fine|blocks|braille picks a more detailed ASCII view (default: the standard ASCII grid).
const {chromium}=require(process.env.REKINDRA_PLAYWRIGHT_PATH||'playwright');
const fs=require('node:fs'),path=require('node:path'),assert=require('node:assert/strict');
const {pathToFileURL}=require('node:url');
(async()=>{
  const input=path.resolve(process.argv[2]),out=path.resolve(process.argv[3]),ascii=!process.argv.includes('--standard'),mono=process.argv.includes('--mono');
  if(mono&&!ascii)throw Error('--mono and --standard cannot be combined');
  const detailArg=process.argv.find(a=>a.startsWith('--detail=')),detail=detailArg?detailArg.slice(9):'standard';
  if(!['standard','fine','blocks','braille'].includes(detail))throw Error('--detail must be standard, fine, blocks or braille');
  if(detailArg&&!ascii)throw Error('--detail and --standard cannot be combined');
  const name=(ascii?(mono?'ascii-mono-scene':'ascii-scene'):'diagnostic-scene')+(detail==='standard'?'':'-'+detail);
  fs.mkdirSync(out,{recursive:true});
  const context=await chromium.launchPersistentContext(path.join(out,'profile'),{channel:'chrome',headless:true,acceptDownloads:true});
  try{
    const page=await context.newPage();
    await page.goto(pathToFileURL(input).href);
    await page.waitForFunction(()=>globalThis.rekindra?.ready);
    await page.locator('#ascii').setChecked(ascii);await page.locator('#asciiColor').setChecked(!mono);
    if(detail!=='standard')await page.locator('#asciiDetail').selectOption(detail);
    const downloading=page.waitForEvent('download');
    const result=await page.evaluate(async()=>{
      const blob=await rekindra.exportVideo({download:false});
      const url=URL.createObjectURL(blob),v=document.createElement('video');v.muted=true;v.src=url;
      const wait=name=>new Promise((resolve,reject)=>{const timer=setTimeout(()=>reject(Error('Decode timeout')),20000);v.addEventListener(name,()=>{clearTimeout(timer);resolve()},{once:true});v.addEventListener('error',()=>{clearTimeout(timer);reject(Error('Decode failed'))},{once:true})});
      await wait('loadeddata');
      const canvas=document.createElement('canvas');canvas.width=v.videoWidth;canvas.height=v.videoHeight;
      // Two decoded moments; the later one keeps the original file name.
      const grab=async part=>{const ready=wait('seeked');v.currentTime=rekindra.scene.duration*part;await ready;canvas.getContext('2d').drawImage(v,0,0);return canvas.toDataURL().split(',')[1]};
      const early=await grab(.25),png=await grab(.6);
      const a=document.createElement('a');a.href=url;a.download='ascii-scene.webm';a.click();
      return {bytes:blob.size,width:v.videoWidth,height:v.videoHeight,duration:v.duration,ascii:document.querySelector('#ascii').checked,mode:document.querySelector('#asciiColor').checked?'color':'mono',detail:document.querySelector('#asciiDetail')?.value||'standard',early,png};
    });
    await (await downloading).saveAs(path.join(out,name+'.webm'));
    assert.equal(result.ascii,ascii);assert.equal(result.mode,mono?'mono':'color');assert.equal(result.detail,detail);if(!ascii){delete result.mode;delete result.detail}assert.equal(result.width,1280);assert.equal(result.height,720);
    assert.ok(result.bytes>1000&&Number.isFinite(result.duration));
    fs.writeFileSync(path.join(out,'decoded-'+name+'-early.png'),Buffer.from(result.early,'base64'));delete result.early;
    fs.writeFileSync(path.join(out,'decoded-'+name+'.png'),Buffer.from(result.png,'base64'));delete result.png;
    result.validation='export/decode only; not deterministic-seek or full acceptance';
    fs.writeFileSync(path.join(out,'result-'+name+'.json'),JSON.stringify(result,null,2));
    fs.writeFileSync(path.join(out,'result.json'),JSON.stringify(result,null,2));console.log(JSON.stringify(result));
  }finally{await context.close()}
})().catch(e=>{console.error(e);process.exitCode=1});
