const {chromium}=require(process.env.REKINDRA_PLAYWRIGHT_PATH||'playwright');
const path=require('node:path'),fs=require('node:fs'),assert=require('node:assert/strict');
const {pathToFileURL}=require('node:url');
(async()=>{
  const root=path.resolve(__dirname,'..'),out=process.env.REKINDRA_BROWSER_OUTPUT||path.join(root,'.local','scene-browser');fs.mkdirSync(out,{recursive:true});
  const input=process.argv[2]||JSON.parse(fs.readFileSync(path.join(root,'.local/scene-fixture/result.json'),'utf8')).path;
  const context=await chromium.launchPersistentContext(path.join(out,'profile'),{channel:'chrome',headless:true,viewport:{width:1400,height:1200},acceptDownloads:true});
  try{
    const page=await context.newPage(),errors=[],requests=[];page.on('pageerror',e=>errors.push(String(e)));
    page.on('request',r=>{if(/^https?:/.test(r.url()))requests.push(r.url())});
    await page.goto(pathToFileURL(input).href);await page.waitForFunction(()=>globalThis.rekindra?.ready,{},{timeout:20000});
    assert.equal(await page.evaluate(()=>globalThis.injected),undefined,'Source text executed');
    const frames=await page.evaluate(()=>{rekindra.renderAt(1);const a=document.querySelector('canvas').toDataURL();rekindra.renderAt(2.5);return [a,document.querySelector('canvas').toDataURL()]});
    assert.notEqual(frames[0],frames[1],'Animation did not change frames');
    const repeat=await page.evaluate(()=>{rekindra.renderAt(.1);rekindra.renderAt(1);return document.querySelector('canvas').toDataURL()});
    assert.equal(repeat,frames[0],'Seeking changed the same frame');
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
    await page.screenshot({path:path.join(out,'scene.png'),fullPage:true});
    await page.locator('#ascii').check();
    assert.notEqual(await page.locator('canvas').evaluate(c=>c.toDataURL()),frames[1]);
    await page.locator('#ascii').uncheck();
    const downloadPromise=page.waitForEvent('download');
    const exportResult=await page.evaluate(async()=>{
      const blob=await rekindra.exportVideo({download:false});
      const url=URL.createObjectURL(blob),video=document.createElement('video');video.muted=true;video.src=url;
      const wait=event=>new Promise((resolve,reject)=>{const t=setTimeout(()=>reject(Error('Video timeout: '+event)),20000);video.addEventListener(event,()=>{clearTimeout(t);resolve()},{once:true});video.addEventListener('error',()=>{clearTimeout(t);reject(Error('Video decode error '+video.error?.message))},{once:true})});
      await wait('loadeddata');const duration=video.duration;
      let done=wait('seeked');video.currentTime=duration*.75;await done;
      const c=document.createElement('canvas');c.width=1280;c.height=720;const x=c.getContext('2d');x.drawImage(video,0,0);
      const sample=Array.from(x.getImageData(640,360,1,1).data);
      await video.play();await new Promise(r=>setTimeout(r,150));video.pause();
      const result={size:blob.size,duration,width:video.videoWidth,height:video.videoHeight,seek:video.currentTime,sample};
      const a=document.createElement('a');a.href=url;a.download='verified-scene.webm';a.click();return result;
    });
    const download=await downloadPromise;await download.saveAs(path.join(out,'verified-scene.webm'));
    assert.ok(Number.isFinite(exportResult.duration)&&Math.abs(exportResult.duration-await page.evaluate(()=>rekindra.scene.duration))<.05);
    assert.equal(exportResult.width,1280);assert.equal(exportResult.height,720);assert.ok(exportResult.seek>0);assert.ok(exportResult.sample.slice(0,3).some(x=>x>0));
    assert.deepEqual(errors,[]);assert.deepEqual(requests,[]);
    fs.writeFileSync(path.join(out,'result.json'),JSON.stringify(exportResult,null,2));console.log(JSON.stringify(exportResult,null,2));
    // Cancellation must reject and leave playback controls usable.
    const cancelled=await page.evaluate(async()=>{const p=rekindra.exportVideo({download:false});setTimeout(()=>rekindra.cancelExport(),10);try{await p;return false}catch(e){return e.message==='Export cancelled'&&!document.querySelector('#export').disabled}});
    assert.equal(cancelled,true,'Cancellation failed');
    const original=fs.readFileSync(input,'utf8');
    const altered=original.replace(/("image_sha256"\s*:\s*")[a-f0-9]{64}/,'$1'+'0'.repeat(64));
    assert.notEqual(altered,original);
    const alteredPath=path.join(out,'corrupted.html');fs.writeFileSync(alteredPath,altered);
    await page.goto(pathToFileURL(alteredPath).href);await page.waitForFunction(()=>globalThis.rekindra);
    assert.equal(await page.evaluate(()=>rekindra.ready),false,'Corrupted embedded data accepted');
    assert.match(await page.evaluate(()=>rekindra.error),/integrity/);
    assert.equal(await page.locator('#export').isDisabled(),true);
  }finally{await context.close()}
})().catch(e=>{console.error(e);process.exitCode=1});
