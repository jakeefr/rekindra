(function(root){
  'use strict';
  const clamp=(x,a,b)=>Math.max(a,Math.min(b,x));
  function noise(n){n=Math.imul(n^n>>>16,0x45d9f3b);n=Math.imul(n^n>>>16,0x45d9f3b);return ((n^n>>>16)>>>0)/4294967296}
  function trackAt(keys,t){
    if(t<=keys[0].at)return {...keys[0]};
    for(let i=1;i<keys.length;i++)if(t<=keys[i].at){
      const a=keys[i-1],b=keys[i],u=(t-a.at)/(b.at-a.at),s=u*u*(3-2*u),out={};
      for(const k of Object.keys(a))out[k]=a[k]+(b[k]-a[k])*s;
      return out;
    }
    return {...keys[keys.length-1]};
  }
  function fragmentPose(c,r,columns,rows,spread,turn,t){
    const bx=(c+.5)/columns-.5,by=(r+.5)/rows-.5;
    const a=turn*Math.PI/180;
    const x=bx*(1+spread*.9)+Math.sin(by*8+t*.5)*spread*.15;
    const y=by*(1+spread*.6)+Math.sin(bx*7+t*.7)*spread*.13;
    const z=spread*(Math.sin(bx*6+by*3+t*.6)*.45+by*.45);
    return {x:x*Math.cos(a)+z*Math.sin(a),y,z:z*Math.cos(a)-x*Math.sin(a)};
  }
  function pose(l,t){
    const u=clamp((t-l.start)/(l.end-l.start),0,1),fade=Math.min(.5,(l.end-l.start)/4);
    let x=l.x,y=l.y,scale=1;
    if(l.motion==='drift'){x+=Math.sin(u*Math.PI*1.5)*.025;y+=Math.cos(u*Math.PI)*.012}
    if(l.motion==='pan')x+=(u-.5)*.06;
    if(l.motion==='rise')y+=(.5-u)*.05;
    if(l.motion==='pulse')scale+=Math.sin(u*Math.PI*2)*.035;
    const key=l.track?.length?trackAt(l.track,t-l.start):null;
    return {active:t>=l.start&&t<l.end,x:key?.x??x,y:key?.y??y,scale:key?.scale??scale,
      spread:key?.spread??0,turn:key?.turn??0,angle:(key?.rotation??l.rotation)*Math.PI/180,
      alpha:(key?.opacity??l.opacity)*clamp((t-l.start)/fade,0,1)*clamp((l.end-t)/fade,0,1)};
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
      }else if(l.kind==='fragments'){
        const img=images[l.asset_id];
        if(img){
          const tiles=[];
          for(let r=0;r<l.rows;r++)for(let c=0;c<l.columns;c++)tiles.push({c,r,...fragmentPose(c,r,l.columns,l.rows,p.spread,p.turn,time-l.start)});
          tiles.sort((a,b)=>b.z-a.z);
          const cover=Math.max(w/img.width,h/img.height),sw=w/cover/l.columns,sh=h/cover/l.rows;
          const ox=(img.width-w/cover)/2,oy=(img.height-h/cover)/2;
          for(const tile of tiles){
            const depth=2.8/(2.8+tile.z),gap=1-p.spread*.16,tw=w/l.columns*depth*gap,th=h/l.rows*depth*gap;
            ctx.save();ctx.translate(tile.x*w*depth,tile.y*h*depth);
            ctx.rotate(p.spread*Math.sin(tile.c*.2+tile.r*.4+time*.4)*.10);
            ctx.drawImage(img,ox+tile.c*sw,oy+tile.r*sh,sw,sh,-tw/2,-th/2,tw+.5,th+.5);
            if(p.spread>.05){ctx.strokeStyle=scene.palette[0]+'44';ctx.lineWidth=.5;ctx.strokeRect(-tw/2,-th/2,tw,th)}
            ctx.restore();
          }
        }
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
  // ASCII view. The ramp ascends by measured ink coverage in a bold monospace face;
  // the four edge glyphs are kept out of it so an outline never reads as shading.
  const ASCII={ramp:' .:~;=+*cvstxneoakhSAm#H8WMB0N&@',columns:200,cellAspect:1.875,gamma:.8,edge:.6,
    mono:[236,240,236],lift:.45,floor:.32,sample:2,low:.02,high:.98,gain:3};
  const asciiGrid=(width,height)=>({columns:ASCII.columns,rows:Math.max(1,Math.round(ASCII.columns*height/width/ASCII.cellAspect))});
  // Brightness 0..1 to a ramp index. Monotonic: a brighter cell never gets a sparser glyph.
  const asciiLevel=lum=>Math.round(Math.pow(clamp(lum,0,1),ASCII.gamma)*(ASCII.ramp.length-1));
  // Frame contrast: spread the darkest and brightest few percent toward the ends of the ramp, by a bounded gain.
  // A flat frame is left as it is. The mapping is increasing, so brightness order inside a frame is kept.
  function asciiTone(lum){
    const bins=new Uint32Array(256);for(let i=0;i<lum.length;i++)bins[Math.round(clamp(lum[i],0,1)*255)]++;
    const rank=share=>{let seen=0;const want=share*lum.length;for(let b=0;b<256;b++){seen+=bins[b];if(seen>=want)return b/255}return 1};
    const lo=rank(ASCII.low),hi=Math.max(lo,rank(ASCII.high)),gain=Math.min(ASCII.gain,hi>lo?1/(hi-lo):ASCII.gain);
    const span=gain*(hi-lo),mid=(lo+hi)/2,centre=clamp(mid,span/2,1-span/2);
    return v=>clamp((v-mid)*gain+centre,0,1);
  }
  // Average factor x factor blocks so thin shapes survive the reduction to one sample per cell.
  function asciiReduce(pixels,width,height,factor){
    const w=Math.floor(width/factor),h=Math.floor(height/factor),out=new Uint8ClampedArray(w*h*4),area=factor*factor;
    for(let y=0;y<h;y++)for(let x=0;x<w;x++)for(let k=0;k<4;k++){
      let sum=0;for(let v=0;v<factor;v++)for(let u=0;u<factor;u++)sum+=pixels[((y*factor+v)*width+x*factor+u)*4+k];
      out[(y*w+x)*4+k]=Math.round(sum/area);
    }
    return out;
  }
  // Pure: RGBA pixels at one sample per cell -> glyphs and glyph colours. No canvas, clock or random input.
  function asciiCells(pixels,columns,rows,mode='color'){
    if(mode!=='color'&&mode!=='mono')throw Error('ASCII mode must be color or mono');
    const n=columns*rows;if(pixels.length<n*4)throw Error('ASCII pixels do not cover the grid');
    const lum=new Float32Array(n),mag=new Float32Array(n),gxs=new Float32Array(n),gys=new Float32Array(n),chars=new Array(n),colors=new Uint8ClampedArray(n*3);
    for(let i=0;i<n;i++)lum[i]=(pixels[i*4]*.2126+pixels[i*4+1]*.7152+pixels[i*4+2]*.0722)/255;
    const tone=asciiTone(lum);for(let i=0;i<n;i++)lum[i]=tone(lum[i]);
    const at=(x,y)=>lum[clamp(y,0,rows-1)*columns+clamp(x,0,columns-1)];
    for(let y=0;y<rows;y++)for(let x=0;x<columns;x++){
      const i=y*columns+x;
      gxs[i]=at(x+1,y-1)+2*at(x+1,y)+at(x+1,y+1)-at(x-1,y-1)-2*at(x-1,y)-at(x-1,y+1);
      gys[i]=at(x-1,y+1)+2*at(x,y+1)+at(x+1,y+1)-at(x-1,y-1)-2*at(x,y-1)-at(x+1,y-1);
      mag[i]=Math.hypot(gxs[i],gys[i]);
    }
    const strength=(x,y)=>x<0||y<0||x>=columns||y>=rows?0:mag[y*columns+x];
    let edges=0;
    for(let y=0;y<rows;y++)for(let x=0;x<columns;x++){
      const i=y*columns+x;let glyph=ASCII.ramp[asciiLevel(lum[i])];
      if(mag[i]>=ASCII.edge){
        // One glyph per crossing, on the darker side of the step, so a bright shape keeps its fill and gains an outline.
        const sx=Math.round(gxs[i]/mag[i]),sy=Math.round(gys[i]/mag[i]);
        if(mag[i]>strength(x-sx,y-sy)&&mag[i]>=strength(x+sx,y+sy)){
          const turn=(Math.atan2(gys[i],gxs[i])*180/Math.PI+180)%180;
          glyph=turn<22.5||turn>=157.5?'|':turn<67.5?'/':turn<112.5?'-':'\\';edges++;
        }
      }
      chars[i]=glyph;
      if(mode==='mono'){colors[i*3]=ASCII.mono[0];colors[i*3+1]=ASCII.mono[1];colors[i*3+2]=ASCII.mono[2]}
      else{
        // Glyph density already carries brightness; lift the colour so dark hues stay legible on the dark ground.
        const r=pixels[i*4],g=pixels[i*4+1],b=pixels[i*4+2],peak=Math.max(r,g,b)/255;
        const gain=peak>0?Math.max(ASCII.floor,Math.pow(peak,ASCII.lift))/peak:0;
        colors[i*3]=Math.round(r*gain);colors[i*3+1]=Math.round(g*gain);colors[i*3+2]=Math.round(b*gain);
      }
    }
    return {columns,rows,mode,chars:chars.join(''),colors,edges};
  }
  let asciiSampler=null;
  function renderAscii(ctx,scratch,mode='color'){
    const W=ctx.canvas.width,H=ctx.canvas.height,{columns,rows}=asciiGrid(W,H),sw=columns*ASCII.sample,sh=rows*ASCII.sample;
    if(!asciiSampler||asciiSampler.width!==sw||asciiSampler.height!==sh){asciiSampler=document.createElement('canvas');asciiSampler.width=sw;asciiSampler.height=sh}
    const s=asciiSampler.getContext('2d',{willReadFrequently:true});s.imageSmoothingEnabled=true;s.imageSmoothingQuality='high';s.drawImage(scratch,0,0,sw,sh);
    const grid=asciiCells(asciiReduce(s.getImageData(0,0,sw,sh).data,sw,sh,ASCII.sample),columns,rows,mode),cw=W/columns,ch=H/rows;
    ctx.save();ctx.setTransform(1,0,0,1,0,0);ctx.globalAlpha=1;ctx.globalCompositeOperation='source-over';
    ctx.fillStyle=mode==='mono'?'#000':'#05080a';ctx.fillRect(0,0,W,H);
    ctx.font=`bold ${(ch*1.08).toFixed(2)}px Consolas,"Cascadia Mono",Menlo,"DejaVu Sans Mono","Liberation Mono",monospace`;ctx.textAlign='center';ctx.textBaseline='middle';
    let last=-1;
    for(let y=0;y<rows;y++)for(let x=0;x<columns;x++){
      const i=y*columns+x,glyph=grid.chars[i];if(glyph===' ')continue;
      const key=grid.colors[i*3]<<16|grid.colors[i*3+1]<<8|grid.colors[i*3+2];
      if(key!==last){ctx.fillStyle=`rgb(${grid.colors[i*3]},${grid.colors[i*3+1]},${grid.colors[i*3+2]})`;last=key}
      ctx.fillText(glyph,(x+.5)*cw,(y+.5)*ch);
    }
    ctx.restore();
  }
  const api={pose,trackAt,fragmentPose,renderScene,renderAscii,asciiCells,asciiGrid,asciiLevel,asciiReduce,asciiTone,ASCII};if(typeof module!=='undefined')module.exports=api;else root.RekindraScene=api;
})(globalThis);
