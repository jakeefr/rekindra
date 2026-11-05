// Development-only visual review of actual decoded video, not scene snapshots.
// Usage: node scripts/review_video.cjs absolute-video-path absolute-output-dir
const {chromium}=require(process.env.REKINDRA_PLAYWRIGHT_PATH||'playwright');
const fs=require('node:fs'),path=require('node:path');
(async()=>{
  const input=path.resolve(process.argv[2]),out=path.resolve(process.argv[3]);
  if(fs.statSync(input).size>100_000_000)throw Error('Review input exceeds 100 MB');
  fs.mkdirSync(out,{recursive:true});
  const context=await chromium.launchPersistentContext(path.join(out,'profile'),{channel:'chrome',headless:true});
  try{
    const page=await context.newPage();await page.setContent('<video muted></video>');
    await page.evaluate(data=>{
      const bytes=Uint8Array.from(atob(data),c=>c.charCodeAt(0));
      document.querySelector('video').src=URL.createObjectURL(new Blob([bytes],{type:'video/webm'}));
    },fs.readFileSync(input).toString('base64'));
    await page.waitForFunction(()=>document.querySelector('video')?.readyState>=2);
    const sheets=await page.evaluate(async()=>{
      const video=document.querySelector('video');video.pause();
      const result=[],overview=document.createElement('canvas');overview.width=1920;overview.height=800;
      const ox=overview.getContext('2d');ox.fillStyle='#111';ox.fillRect(0,0,1920,800);
      for(let sheet=0;sheet<4;sheet++){
        const c=document.createElement('canvas');c.width=1536;c.height=636;const x=c.getContext('2d');
        x.fillStyle='#111';x.fillRect(0,0,c.width,c.height);
        for(let j=0;j<6;j++){
          const t=(sheet*6+j+.25)*video.duration/24;
          await new Promise((resolve,reject)=>{
            const timeout=setTimeout(()=>reject(Error('Video seek timeout')),15000);
            video.addEventListener('seeked',()=>{clearTimeout(timeout);resolve()},{once:true});video.currentTime=t;
          });
          const px=j%3*512,py=Math.floor(j/3)*318;
          x.drawImage(video,px,py,512,288);
          x.fillStyle='#eee';x.font='16px monospace';x.fillText(t.toFixed(2)+' s',px+12,py+309);
          const n=sheet*6+j,opx=n%6*320,opy=Math.floor(n/6)*200;
          ox.drawImage(video,opx,opy,320,180);ox.fillStyle='#eee';ox.font='12px monospace';ox.fillText(t.toFixed(2)+' s',opx+8,opy+195);
        }
        result.push(c.toDataURL().split(',')[1]);
      }result.push(overview.toDataURL().split(',')[1]);return result;
    });
    sheets.forEach((data,i)=>fs.writeFileSync(path.join(out,i===4?'decoded-overview.png':`decoded-${i+1}.png`),Buffer.from(data,'base64')));
    console.log('Saved 24 decoded frames across 4 review sheets and one overview.');
  }finally{await context.close()}
})().catch(e=>{console.error(e);process.exitCode=1});
