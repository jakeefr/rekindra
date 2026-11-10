(async function(){
  'use strict';
  const data=JSON.parse(document.querySelector('#payload').textContent),scene=data.scene;
  const $=id=>document.getElementById(id),canvas=$('stage'),ctx=canvas.getContext('2d'),images={};
  let time=0,playing=false,start=0,exporting=false,cancelled=false,world=null;
  const renderQuality=()=>world?{requestedScale:world.requestedScale,actualScale:world.sampleScale,limited:world.sampleScale<world.requestedScale}:null;
  const qualityNotice=()=>renderQuality()?.limited?' Using standard quality because this graphics device cannot render the higher-quality frame.':'';
  const scratch=document.createElement('canvas');scratch.width=1280;scratch.height=720;const sc=scratch.getContext('2d');
  $('title').textContent=scene.title;$('mood').textContent=scene.mood.toUpperCase();$('reason').textContent=scene.reason;
  $('seek').max=scene.duration;const named=v=>typeof v==='string'&&v&&v!=='not-attested';
  // The plugin cannot verify which model called it, so an unnamed one is said in plain words, not as a field value.
  $('model').textContent=!data.model.model?'Creative plan: local authored fixture':named(data.model.provider)&&named(data.model.model)?`Creative plan: ${data.model.provider} / ${data.model.model}`:`Creative plan: ${data.model.origin==='caller-revised'?'revised':'written'} by the AI agent in this session. Which model it was is not recorded.`;
  const asciiMode=()=>$('asciiColor').checked?'color':'mono',asciiDetail=()=>({detail:$('asciiDetail')?.value||'standard'});
  function draw(t,ascii=$('ascii').checked,target=ctx,mode=asciiMode(),detail=asciiDetail()){
    if(world){const frame=world.render(t);if(ascii)RekindraScene.renderAscii(target,frame,mode,detail);else target.drawImage(frame,0,0);return}
    if(ascii){RekindraScene.renderScene(sc,scene,images,t);RekindraScene.renderAscii(target,scratch,mode,detail)}
    else RekindraScene.renderScene(target,scene,images,t);
  }
  function display(t){time=Math.max(0,Math.min(scene.duration-.0001,t));draw(time);$('seek').value=time;$('time').textContent=`${time.toFixed(1)} / ${scene.duration}s`}
  function stop(){playing=false;$('play').textContent='Play'}
  // Percent of a 640x360 review frame that is near-white where no glow surface lights it, sampled at the same
  // 128x72 nearest-neighbour points and level (190) as the sheet measurement, so it never exceeds that share.
  function offEmitterWhite(fx,mask){
    const px=fx.getImageData(0,0,640,360).data,sx=mask.width/640,sy=mask.height/360;let count=0;
    for(let y=0;y<72;y++)for(let x=0;x<128;x++){
      const fxX=x*5+2,fxY=y*5+2,at=(fxY*640+fxX)*4;
      if(Math.min(px[at],px[at+1],px[at+2])<190)continue;
      let lit=0;for(let j=Math.floor(fxY*sy);j<Math.ceil((fxY+1)*sy);j++)for(let i=Math.floor(fxX*sx);i<Math.ceil((fxX+1)*sx);i++)lit=Math.max(lit,mask.data[j*mask.width+i]);
      if(lit<64)count++;   // a glow surface adding a quarter of full scale or more here owns this pixel
    }
    return Math.round(count*1000/(128*72))/10;
  }
  function reviewFrames(){
    if(exporting)throw Error('Wait for video export before capturing review frames');
    stop();const saved=time,c=document.createElement('canvas');c.width=1280;c.height=1128;
    const x=c.getContext('2d'),times=[],frames=[],offEmitter=[],f=document.createElement('canvas');f.width=640;f.height=360;
    const fx=f.getContext('2d');x.fillStyle='#111';x.fillRect(0,0,c.width,c.height);
    try{
      // Grain differs every frame, so it would make a motionless scene measure as moving. Review without it.
      if(world)world.setGrain(false);
      for(let i=0;i<6;i++){
        const t=(i+.5)*scene.duration/6;times.push(t);draw(t,false,sc);
        const mask=world?world.emitterMask(t):null;
        const px=i%2*640,py=Math.floor(i/2)*376;
        x.drawImage(scratch,px,py,640,360);x.fillStyle='#eee';x.font='12px monospace';x.fillText(t.toFixed(2)+' s',px+8,py+372);
        // Each frame alone, small enough for a vision model that times out on the whole sheet.
        fx.drawImage(scratch,0,0,640,360);frames.push(f.toDataURL('image/png').split(',')[1]);
        if(mask)offEmitter.push(offEmitterWhite(fx,mask));
      }
      const result={kind:'rendered-frame-review',times,width:c.width,height:c.height,renderQuality:renderQuality(),png:c.toDataURL('image/png').split(',')[1],frames};
      if(offEmitter.length===6)result.whiteOffEmitter=offEmitter;
      return result;
    }finally{if(world)world.setGrain(true);display(saved)}
  }
  function reportReview(result){
    const el=document.createElement('script');el.id='rekindra-review-result';el.type='application/json';
    el.textContent=JSON.stringify(result);document.body.append(el);
  }
  function tick(now){try{if(playing&&!exporting)display(((now-start)/1000)%scene.duration)}catch(e){stop();$('status').textContent=e.message;$('export').disabled=true}requestAnimationFrame(tick)}
  async function exportVideo({download=true}={}){
    if(data.inspection_only)throw Error('Inspection view only. Export from the saved presentation scene.');
    if(data.export_locked)throw Error('Draft preview. Run rekindra_export to clear this scene for video export.');
    if(exporting)throw Error('An export is already running');
    if(!globalThis.VideoEncoder)throw Error('This browser does not provide WebCodecs. Use a supported Chromium browser.');
    // Preserve smooth gradients in opening keyframes; 3 Mbps produced visible blocks.
    const config={codec:'vp8',width:1280,height:720,bitrate:8_000_000,framerate:30};
    if(!(await VideoEncoder.isConfigSupported(config)).supported)throw Error('Native VP8 encoding is unavailable in this browser.');
    stop();exporting=true;cancelled=false;$('export').disabled=true;$('play').disabled=true;$('seek').disabled=true;$('ascii').disabled=true;$('asciiColor').disabled=true;$('asciiDetail')&&($('asciiDetail').disabled=true);$('cancel').hidden=false;
    const wasTime=time,ascii=$('ascii').checked,mode=asciiMode(),detail=asciiDetail(),chunks=[],out=document.createElement('canvas');out.width=1280;out.height=720;
    const oc=out.getContext('2d');let failure,totalBytes=0;
    const encoder=new VideoEncoder({output(c){const bytes=new Uint8Array(c.byteLength);c.copyTo(bytes);totalBytes+=bytes.length;if(totalBytes>100_000_000){failure=Error('Encoded video exceeds 100 MB limit');return}chunks.push({timestamp:c.timestamp,type:c.type,data:bytes})},error(e){failure=e}});
    try{
      encoder.configure(config);const frames=Math.round(scene.duration*30);
      for(let i=0;i<frames;i++){
        if(cancelled)throw Error('Export cancelled');if(failure)throw failure;
        draw(i/30,ascii,oc,mode,detail);const frame=new VideoFrame(out,{timestamp:Math.round(i*1_000_000/30),duration:33333});
        try{encoder.encode(frame,{keyFrame:i%30===0})}finally{frame.close()}
        if(encoder.encodeQueueSize>8)await encoder.flush();
        if(i%10===0){$('status').textContent=`Rendering ${i+1} of ${frames} frames...`;await new Promise(r=>setTimeout(r,0))}
      }
      await encoder.flush();if(failure)throw failure;if(cancelled)throw Error('Export cancelled');
      if(chunks.length!==frames)throw Error('Encoder did not return every frame');
      const bytes=RekindraWebM.muxWebM(chunks,1280,720,frames/30*1000),blob=new Blob([bytes],{type:'video/webm'});
      if(download){const url=URL.createObjectURL(blob),a=document.createElement('a');a.href=url;a.download='rekindra-scene.webm';a.click();setTimeout(()=>URL.revokeObjectURL(url),60_000)}
      $('status').textContent=`Video ready. ${frames} frames, ${(blob.size/1024/1024).toFixed(1)} MB.${qualityNotice()}`;return blob;
    }finally{if(encoder.state!=='closed')encoder.close();exporting=false;$('export').disabled=false;$('play').disabled=false;$('seek').disabled=false;$('ascii').disabled=false;$('asciiColor').disabled=false;$('asciiDetail')&&($('asciiDetail').disabled=false);$('cancel').hidden=true;display(wasTime)}
  }
  try{
    for(const source of data.sources){
      if(!/^data:image\/(png|jpeg);base64,/.test(source.url)||source.url.length>2_700_000)throw Error('Invalid embedded source');
      const bytes=Uint8Array.from(atob(source.url.split(',')[1]),c=>c.charCodeAt(0));
      const digest=await crypto.subtle.digest('SHA-256',bytes);
      const hash=Array.from(new Uint8Array(digest),b=>b.toString(16).padStart(2,'0')).join('');
      if(hash!==source.image_sha256)throw Error('Source image integrity check failed');
      const img=new Image();
      // Image.decode() can remain pending after headless virtual time expires.
      // A load event participates in document loading and completes before DOM capture.
      await new Promise((resolve,reject)=>{img.onload=resolve;img.onerror=()=>reject(Error('Source image could not be loaded'));img.src=source.url});
      if(img.width*img.height>20_000_000)throw Error('Source image exceeds pixel budget');images[source.asset_id]=img;
      const card=document.createElement('div');card.className='source';const thumb=img.cloneNode(),caption=document.createElement('span');thumb.alt=source.name;caption.textContent=`${source.name} · ${source.kind} · SHA-256 ${source.source_sha256}`;card.append(thumb,caption);$('sources').append(card)}
    if(scene.schema_version===2){
      world=RekindraWorld.createRenderer(scene,data.programs,{images});
      for(const o of scene.objects){if(!o.material_image)continue;const from=data.sources.find(s=>s.asset_id===o.material_image.asset_id),c=o.material_image.crop.map(x=>Math.round(x*100));
        const p=document.createElement('p');p.textContent=`Recovered material: surface "${o.id}" takes its texture from a crop of ${from?from.name:'a source image'} (left ${c[0]}%, top ${c[1]}%, width ${c[2]}%, height ${c[3]}%). The shape it covers is created.`;$('sources').append(p)}
      for(const ref of scene.references){const p=document.createElement('p');p.textContent=`Agent interpretation — observed: ${ref.observed} Created: ${ref.created}`;$('sources').append(p)}
      for(const ref of scene.text_references||[]){const p=document.createElement('p');p.textContent=`Agent interpretation of recovered text: ${ref.interpretation}`;$('sources').append(p)}
    }
    display(Math.min(.8,scene.duration/4));$('status').textContent='Ready. Everything needed for playback is in this file.';
    if(data.inspection_only){$('status').textContent='Inspection view only. Saved scene and presentation camera are unchanged.';$('export').disabled=true;}
    if(data.export_locked){$('status').textContent='Draft preview. Use rekindra_export to get the file that can save video.';$('export').disabled=true;}
    $('status').textContent+=qualityNotice();
    $('play').onclick=()=>{if(playing)stop();else{playing=true;start=performance.now()-time*1000;$('play').textContent='Pause'}};
    $('seek').oninput=()=>{stop();display(Number($('seek').value))};$('ascii').onchange=$('asciiColor').onchange=()=>display(time);if($('asciiDetail'))$('asciiDetail').onchange=()=>display(time);
    $('export').onclick=()=>exportVideo().catch(e=>$('status').textContent=e.message);
    $('cancel').onclick=()=>cancelled=true;
    globalThis.rekindra={ready:true,scene,data,renderQuality:renderQuality(),renderAt:display,exportVideo,reviewFrames,cancelExport:()=>cancelled=true};
    if(new URLSearchParams(location.search).get('rekindra_review')==='1')reportReview({ok:true,result:reviewFrames()});
    else requestAnimationFrame(tick);
  }catch(e){$('status').textContent=`Cannot open scene: ${e.message}`;$('play').disabled=true;$('export').disabled=true;globalThis.rekindra={ready:false,error:e.message};
    if(new URLSearchParams(location.search).get('rekindra_review')==='1')reportReview({ok:false,error:'Scene rendering failed. Check source integrity, graphics support and scene geometry.'});
  }
})();
