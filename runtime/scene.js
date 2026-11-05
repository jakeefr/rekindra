(function(root){
  'use strict';
  const clamp=(x,a,b)=>Math.max(a,Math.min(b,x));
  function noise(n){n=Math.imul(n^n>>>16,0x45d9f3b);n=Math.imul(n^n>>>16,0x45d9f3b);return ((n^n>>>16)>>>0)/4294967296}
  function pose(l,t){
    const u=clamp((t-l.start)/(l.end-l.start),0,1),fade=Math.min(.5,(l.end-l.start)/4);
    let x=l.x,y=l.y,scale=1;
    if(l.motion==='drift'){x+=Math.sin(u*Math.PI*1.5)*.025;y+=Math.cos(u*Math.PI)*.012}
    if(l.motion==='pan')x+=(u-.5)*.06;
    if(l.motion==='rise')y+=(.5-u)*.05;
    if(l.motion==='pulse')scale+=Math.sin(u*Math.PI*2)*.035;
    return {active:t>=l.start&&t<l.end,x,y,scale,angle:l.rotation*Math.PI/180,
      alpha:l.opacity*clamp((t-l.start)/fade,0,1)*clamp((l.end-t)/fade,0,1)};
  }
  function textLines(ctx,text,maxWidth){
    const result=[];let line='';
    for(const word of text.split(/\s+/)){const candidate=line?line+' '+word:word;
      if(line&&ctx.measureText(candidate).width>maxWidth){result.push(line);line=word}else line=candidate;
    }
    if(line)result.push(line);return result;
  }
  function renderScene(ctx,scene,images,time){
    const W=scene.width,H=scene.height;
    ctx.save();ctx.setTransform(1,0,0,1,0,0);ctx.globalAlpha=1;ctx.fillStyle=scene.background;ctx.fillRect(0,0,W,H);
    const glow=ctx.createRadialGradient(W*.5,H*.3,0,W*.5,H*.5,W*.7);
    glow.addColorStop(0,scene.palette[0]+'22');glow.addColorStop(1,scene.background+'00');
    ctx.fillStyle=glow;ctx.fillRect(0,0,W,H);
    scene.layers.forEach((l,index)=>{
      const p=pose(l,time);if(!p.active||p.alpha<=0)return;
      ctx.save();ctx.globalAlpha=p.alpha;ctx.translate(p.x*W,p.y*H);ctx.rotate(p.angle);ctx.scale(p.scale,p.scale);
      const w=l.width*W,h=l.height*H;
      if(l.kind==='image'){
        const img=images[l.asset_id];
        if(img){ctx.beginPath();ctx.roundRect(-w/2,-h/2,w,h,Math.min(10,w/20));ctx.clip();
          const s=Math.max(w/img.width,h/img.height);ctx.drawImage(img,-img.width*s/2,-img.height*s/2,img.width*s,img.height*s)}
      }else if(l.kind==='text'){
        let size=l.font_size;ctx.font=`${size}px ${l.font}`;
        while(size>16&&textLines(ctx,l.text,w).length*size*1.3>h){size--;ctx.font=`${size}px ${l.font}`}
        const lines=textLines(ctx,l.text,w);ctx.fillStyle=l.color;ctx.textAlign='center';ctx.textBaseline='middle';
        lines.forEach((line,i)=>ctx.fillText(line,0,(i-(lines.length-1)/2)*size*1.3,w));
      }else if(l.kind==='particles'){
        ctx.fillStyle=l.color;
        for(let i=0;i<l.count;i++){
          const seed=scene.seed+index*1000+i*7,phase=noise(seed)*Math.PI*2;
          const x=(noise(seed+1)-.5)*w+Math.sin(time*.25+phase)*15;
          const y=((noise(seed+2)+time*(.005+noise(seed+3)*.015))%1-.5)*h;
          ctx.globalAlpha=p.alpha*(.15+.55*noise(seed+4));ctx.beginPath();ctx.arc(x,y,.6+noise(seed+5)*2.2,0,Math.PI*2);ctx.fill();
        }
      }
      ctx.restore();
    });ctx.restore();
  }
  function renderAscii(ctx,scratch){
    const columns=110,rows=Math.round(columns*scratch.height/scratch.width*.55),sample=document.createElement('canvas');
    sample.width=columns;sample.height=rows;const s=sample.getContext('2d',{willReadFrequently:true});s.drawImage(scratch,0,0,columns,rows);
    const pixels=s.getImageData(0,0,columns,rows).data,chars=' .:-=+*#%@',cw=scratch.width/columns,ch=scratch.height/rows;
    ctx.fillStyle='#080f12';ctx.fillRect(0,0,scratch.width,scratch.height);ctx.font=`${ch}px monospace`;ctx.textBaseline='top';
    for(let y=0;y<rows;y++)for(let x=0;x<columns;x++){
      const i=(y*columns+x)*4,lum=(pixels[i]*.2126+pixels[i+1]*.7152+pixels[i+2]*.0722)/255;
      ctx.fillStyle=`rgb(${pixels[i]},${pixels[i+1]},${pixels[i+2]})`;ctx.fillText(chars[Math.min(9,Math.floor(lum*10))],x*cw,y*ch,cw);
    }
  }
  const api={pose,renderScene,renderAscii};if(typeof module!=='undefined')module.exports=api;else root.RekindraScene=api;
})(globalThis);
