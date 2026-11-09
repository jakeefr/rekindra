const {chromium}=require(process.env.REKINDRA_PLAYWRIGHT_PATH||'playwright');
const path=require('node:path'),fs=require('node:fs'),assert=require('node:assert/strict');
const {pathToFileURL}=require('node:url');
const {probeMotion}=require('./motion_probe.cjs');
const digest=value=>require('node:crypto').createHash('sha256').update(value).digest('hex');
(async()=>{
  const root=path.resolve(__dirname,'..'),out=process.env.REKINDRA_BROWSER_OUTPUT||path.join(root,'.local','scene-browser');fs.mkdirSync(out,{recursive:true});
  const input=process.argv[2]||JSON.parse(fs.readFileSync(path.join(root,'.local/scene-fixture/result.json'),'utf8')).path;
  const reference=process.env.REKINDRA_REFERENCE_BACKEND;
  if(reference && reference!=='swiftshader')throw Error('Unknown reference backend');
  const context=await chromium.launchPersistentContext(path.join(out,'profile'),{channel:'chrome',headless:true,viewport:{width:1400,height:1200},acceptDownloads:true,
    args:reference?['--use-angle=swiftshader','--enable-unsafe-swiftshader']:[]});
  try{
    const page=await context.newPage(),errors=[],requests=[];page.on('pageerror',e=>errors.push(String(e)));
    page.on('request',r=>{if(/^https?:/.test(r.url()))requests.push(r.url())});
    await page.goto(pathToFileURL(input).href);await page.waitForFunction(()=>globalThis.rekindra?.ready,{},{timeout:20000});
    const backend=await page.evaluate(()=>{const gl=document.createElement('canvas').getContext('webgl2'),e=gl.getExtension('WEBGL_debug_renderer_info');return e?gl.getParameter(e.UNMASKED_RENDERER_WEBGL):gl.getParameter(gl.RENDERER)});
    fs.writeFileSync(path.join(out,'backend.json'),JSON.stringify({requested:reference||'default',actual:backend,scope:reference?'development reference only; not default-browser acceptance':'default browser'},null,2));
    assert.equal(await page.evaluate(()=>globalThis.injected),undefined,'Source text executed');
    const frames=await page.evaluate(()=>{rekindra.renderAt(1);const a=document.querySelector('canvas').toDataURL();rekindra.renderAt(2.5);return [a,document.querySelector('canvas').toDataURL()]});
    const motion=await page.evaluate(probeMotion,{});
    assert.equal(motion.changed,true,'Animation did not change sampled timeline frames');
    const repeat=await page.evaluate(()=>{rekindra.renderAt(.1);rekindra.renderAt(1);return document.querySelector('canvas').toDataURL()});
    // Compare decoded pixels: PNG encoding bytes are not the rendering contract.
    const samePixels=await page.evaluate(async([a,b])=>{
      const pixels=async url=>{const img=new Image();img.src=url;await img.decode();const c=document.createElement('canvas');c.width=img.width;c.height=img.height;const x=c.getContext('2d');x.drawImage(img,0,0);return x.getImageData(0,0,c.width,c.height).data};
      const x=await pixels(a),y=await pixels(b);let changed=0,maxDelta=0;
      for(let i=0;i<x.length;i++){const d=Math.abs(x[i]-y[i]);if(d)changed++;maxDelta=Math.max(maxDelta,d)}
      return {changed,maxDelta};
    },[frames[0],repeat]);
    if(digest(repeat)!==digest(frames[0]))console.log(JSON.stringify({pngEncodingDiffers:true,...samePixels}));
    assert.equal(samePixels.changed,0,'Seeking changed rendered pixels');
    if(process.env.REKINDRA_WORLD_STUDY){
      const result=await page.evaluate(()=>{
        if(rekindra.scene.schema_version!==2)throw Error('Not a generated world');
        let imageDraws=0;const original=CanvasRenderingContext2D.prototype.drawImage;
        CanvasRenderingContext2D.prototype.drawImage=function(...args){if(args[0] instanceof HTMLImageElement)imageDraws++;return original.apply(this,args)};
        try{for(let i=0;i<24;i++)rekindra.renderAt(rekindra.scene.duration*(i+.5)/24);return {imageDraws}}
        finally{CanvasRenderingContext2D.prototype.drawImage=original;rekindra.renderAt(2.5)}
      });
      assert.equal(result.imageDraws,0,'Source pixels were drawn in world mode');
      const independent=await page.evaluate(probeMotion,{fixedCamera:true});
      fs.writeFileSync(path.join(out,'motion-probe.json'),JSON.stringify({motion,independent},null,2));
      assert.equal(independent.changed,true,'No visual motion detected with the camera fixed');
    }
    if(process.env.REKINDRA_MOTION_STUDY){
      assert.equal(await page.evaluate(()=>rekindra.scene.layers.some(l=>l.kind==='text')),false);
      const sheet=await page.evaluate(()=>{
        const c=document.createElement('canvas');c.width=1280;c.height=1080;const x=c.getContext('2d');
        [1,3,5,7,9,11].forEach((t,i)=>{rekindra.renderAt(t);x.drawImage(document.querySelector('#stage'),i%2*640,Math.floor(i/2)*360,640,360)});
        return c.toDataURL().split(',')[1];
      });
      fs.writeFileSync(path.join(out,'contact-sheet.png'),Buffer.from(sheet,'base64'));
      const change=await page.evaluate(()=>{
        const c=document.querySelector('#stage'),x=c.getContext('2d');rekindra.renderAt(1);const a=x.getImageData(0,0,1280,720).data;
        rekindra.renderAt(5);const b=x.getImageData(0,0,1280,720).data;let changed=0;
        for(let i=0;i<a.length;i+=4)if(Math.abs(a[i]-b[i])+Math.abs(a[i+1]-b[i+1])+Math.abs(a[i+2]-b[i+2])>35)changed++;
        return changed/(1280*720);
      });
      assert.ok(change>.15,'Motion study must change a substantial part of the frame');
      console.log(JSON.stringify({motionChangedFraction:change}));
    }
    await page.evaluate(()=>rekindra.renderAt(2.5));
    const normalBeforeAscii=await page.locator('canvas').evaluate(c=>c.toDataURL());
    await page.screenshot({path:path.join(out,'scene.png'),fullPage:true});
    await page.locator('#ascii').check();
    assert.notEqual(await page.locator('canvas').evaluate(c=>c.toDataURL()),normalBeforeAscii);
    await page.locator('#ascii').uncheck();
    const downloadPromise=page.waitForEvent('download',{timeout:reference?300000:30000});
    const exportResult=await page.evaluate(async(worldStudy)=>{
      const blob=await rekindra.exportVideo({download:false});
      const url=URL.createObjectURL(blob),video=document.createElement('video');video.muted=true;video.src=url;
      const wait=event=>new Promise((resolve,reject)=>{const t=setTimeout(()=>reject(Error('Video timeout: '+event)),20000);video.addEventListener(event,()=>{clearTimeout(t);resolve()},{once:true});video.addEventListener('error',()=>{clearTimeout(t);reject(Error('Video decode error '+video.error?.message))},{once:true})});
      await wait('loadeddata');const duration=video.duration;
      let done=wait('seeked');video.currentTime=duration*.75;await done;
      const c=document.createElement('canvas');c.width=1280;c.height=720;const x=c.getContext('2d');x.drawImage(video,0,0);
      const sample=Array.from(x.getImageData(640,360,1,1).data);
      await video.play();await new Promise(r=>setTimeout(r,150));video.pause();
      const result={size:blob.size,duration,width:video.videoWidth,height:video.videoHeight,seek:video.currentTime,sample};
      if(worldStudy){
        const sheet=document.createElement('canvas');sheet.width=1280;sheet.height=1080;const sx=sheet.getContext('2d');
        for(let i=0;i<6;i++){const ready=wait('seeked');video.currentTime=(i+.5)*duration/6;await ready;sx.drawImage(video,i%2*640,Math.floor(i/2)*360,640,360)}
        result.decodedContactSheet=sheet.toDataURL().split(',')[1];
      }
      const a=document.createElement('a');a.href=url;a.download='verified-scene.webm';a.click();return result;
    },Boolean(process.env.REKINDRA_WORLD_STUDY));
    const download=await downloadPromise;await download.saveAs(path.join(out,'verified-scene.webm'));
    if(exportResult.decodedContactSheet){fs.writeFileSync(path.join(out,'decoded-contact-sheet.png'),Buffer.from(exportResult.decodedContactSheet,'base64'));delete exportResult.decodedContactSheet}
    // Preserve failed decode evidence too; this is diagnostic data, not a pass marker.
    fs.writeFileSync(path.join(out,'export-observation.json'),JSON.stringify(exportResult,null,2));
    assert.ok(Number.isFinite(exportResult.duration)&&Math.abs(exportResult.duration-await page.evaluate(()=>rekindra.scene.duration))<.05);
    assert.equal(exportResult.width,1280);assert.equal(exportResult.height,720);assert.ok(exportResult.seek>0);assert.ok(exportResult.sample.slice(0,3).some(x=>x>0));
    assert.deepEqual(errors,[]);assert.deepEqual(requests,[]);
    fs.writeFileSync(path.join(out,'result.json'),JSON.stringify(exportResult,null,2));console.log(JSON.stringify(exportResult,null,2));
    // Cancellation must reject and leave playback controls usable.
    const cancelled=await page.evaluate(async()=>{const p=rekindra.exportVideo({download:false});setTimeout(()=>rekindra.cancelExport(),10);try{await p;return false}catch(e){return e.message==='Export cancelled'&&!document.querySelector('#export').disabled}});
    assert.equal(cancelled,true,'Cancellation failed');
    const original=fs.readFileSync(input,'utf8');
    // The player's integrity check hashes embedded images; a world built from text alone embeds none.
    if(!/"sources"\s*:\s*\[\s*\]/.test(original)){
      const altered=original.replace(/("image_sha256"\s*:\s*")[a-f0-9]{64}/,'$1'+'0'.repeat(64));
      assert.notEqual(altered,original);
      const alteredPath=path.join(out,'corrupted.html');fs.writeFileSync(alteredPath,altered);
      await page.goto(pathToFileURL(alteredPath).href);await page.waitForFunction(()=>globalThis.rekindra);
      assert.equal(await page.evaluate(()=>rekindra.ready),false,'Corrupted embedded data accepted');
      assert.match(await page.evaluate(()=>rekindra.error),/integrity/);
      assert.equal(await page.locator('#export').isDisabled(),true);
    }
  }finally{await context.close()}
})().catch(e=>{console.error(e);process.exitCode=1});
