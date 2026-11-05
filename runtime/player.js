(async function(){
  'use strict';
  const data=JSON.parse(document.querySelector('#payload').textContent),scene=data.scene;
  const $=id=>document.getElementById(id),canvas=$('stage'),ctx=canvas.getContext('2d'),images={};
  let time=0,playing=false,start=0,exporting=false,cancelled=false;
  const scratch=document.createElement('canvas');scratch.width=1280;scratch.height=720;const sc=scratch.getContext('2d');
  $('title').textContent=scene.title;$('mood').textContent=scene.mood.toUpperCase();$('reason').textContent=scene.reason;
  $('seek').max=scene.duration;$('model').textContent=data.model.model?`Creative plan: ${data.model.provider} / ${data.model.model}`:'Creative plan: local authored fixture';
  function draw(t,ascii=$('ascii').checked,target=ctx){
    if(ascii){RekindraScene.renderScene(sc,scene,images,t);RekindraScene.renderAscii(target,scratch)}
    else RekindraScene.renderScene(target,scene,images,t);
  }
  function display(t){time=Math.max(0,Math.min(scene.duration-.0001,t));draw(time);$('seek').value=time;$('time').textContent=`${time.toFixed(1)} / ${scene.duration}s`}
  function stop(){playing=false;$('play').textContent='Play'}
  function tick(now){if(playing&&!exporting){display(((now-start)/1000)%scene.duration)}requestAnimationFrame(tick)}
  async function exportVideo({download=true}={}){
    if(exporting)throw Error('An export is already running');
    if(!globalThis.VideoEncoder)throw Error('This browser does not provide WebCodecs. Use a supported Chromium browser.');
    const config={codec:'vp8',width:1280,height:720,bitrate:3_000_000,framerate:30};
    if(!(await VideoEncoder.isConfigSupported(config)).supported)throw Error('Native VP8 encoding is unavailable in this browser.');
    stop();exporting=true;cancelled=false;$('export').disabled=true;$('play').disabled=true;$('seek').disabled=true;$('ascii').disabled=true;$('cancel').hidden=false;
    const wasTime=time,ascii=$('ascii').checked,chunks=[],out=document.createElement('canvas');out.width=1280;out.height=720;
    const oc=out.getContext('2d');let failure,totalBytes=0;
    const encoder=new VideoEncoder({output(c){const bytes=new Uint8Array(c.byteLength);c.copyTo(bytes);totalBytes+=bytes.length;if(totalBytes>100_000_000){failure=Error('Encoded video exceeds 100 MB limit');return}chunks.push({timestamp:c.timestamp,type:c.type,data:bytes})},error(e){failure=e}});
    try{
      encoder.configure(config);const frames=Math.round(scene.duration*30);
      for(let i=0;i<frames;i++){
        if(cancelled)throw Error('Export cancelled');if(failure)throw failure;
        draw(i/30,ascii,oc);const frame=new VideoFrame(out,{timestamp:Math.round(i*1_000_000/30),duration:33333});
        try{encoder.encode(frame,{keyFrame:i%30===0})}finally{frame.close()}
        if(encoder.encodeQueueSize>8)await encoder.flush();
        if(i%10===0){$('status').textContent=`Rendering ${i+1} of ${frames} frames...`;await new Promise(r=>setTimeout(r,0))}
      }
      await encoder.flush();if(failure)throw failure;if(cancelled)throw Error('Export cancelled');
      if(chunks.length!==frames)throw Error('Encoder did not return every frame');
      const bytes=RekindraWebM.muxWebM(chunks,1280,720,frames/30*1000),blob=new Blob([bytes],{type:'video/webm'});
      if(download){const url=URL.createObjectURL(blob),a=document.createElement('a');a.href=url;a.download='rekindra-scene.webm';a.click();setTimeout(()=>URL.revokeObjectURL(url),60_000)}
      $('status').textContent=`Video ready. ${frames} frames, ${(blob.size/1024/1024).toFixed(1)} MB.`;return blob;
    }finally{if(encoder.state!=='closed')encoder.close();exporting=false;$('export').disabled=false;$('play').disabled=false;$('seek').disabled=false;$('ascii').disabled=false;$('cancel').hidden=true;display(wasTime)}
  }
  try{
    for(const source of data.sources){
      if(!/^data:image\/(png|jpeg);base64,/.test(source.url)||source.url.length>2_700_000)throw Error('Invalid embedded source');
      const bytes=Uint8Array.from(atob(source.url.split(',')[1]),c=>c.charCodeAt(0));
      const digest=await crypto.subtle.digest('SHA-256',bytes);
      const hash=Array.from(new Uint8Array(digest),b=>b.toString(16).padStart(2,'0')).join('');
      if(hash!==source.image_sha256)throw Error('Source image integrity check failed');
      const img=new Image();img.src=source.url;await img.decode();if(img.width*img.height>20_000_000)throw Error('Source image exceeds pixel budget');images[source.asset_id]=img;
      const card=document.createElement('div');card.className='source';const thumb=img.cloneNode(),caption=document.createElement('span');thumb.alt=source.name;caption.textContent=`${source.name} · ${source.kind} · SHA-256 ${source.source_sha256}`;card.append(thumb,caption);$('sources').append(card)}
    display(Math.min(.8,scene.duration/4));$('status').textContent='Ready. Everything needed for playback is in this file.';
    $('play').onclick=()=>{if(playing)stop();else{playing=true;start=performance.now()-time*1000;$('play').textContent='Pause'}};
    $('seek').oninput=()=>{stop();display(Number($('seek').value))};$('ascii').onchange=()=>display(time);
    $('export').onclick=()=>exportVideo().catch(e=>$('status').textContent=e.message);
    $('cancel').onclick=()=>cancelled=true;
    globalThis.rekindra={ready:true,scene,data,renderAt:display,exportVideo,cancelExport:()=>cancelled=true};requestAnimationFrame(tick);
  }catch(e){$('status').textContent=`Cannot open scene: ${e.message}`;$('play').disabled=true;$('export').disabled=true;globalThis.rekindra={ready:false,error:e.message}}
})();
