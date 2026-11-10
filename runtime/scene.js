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
  // Optional detail levels; 'standard' is the original view and stays as it was. sub = samples per cell across and down:
  // 'fine' is a denser grid with the longer ramp and stronger outlines, 'blocks' draws two stacked half cells
  // (upper/lower half block with a foreground and background colour), 'braille' draws a 2x4 dot matrix per cell.
  const ASCII={ramp:' .:~;=+*cvstxneoakhSAm#H8WMB0N&@',columns:200,cellAspect:1.875,gamma:.8,edge:.6,
    mono:[236,240,236],lift:.45,floor:.32,sample:2,low:.02,high:.98,gain:3,
    richRamp:' .`\',:^";~!i=+<>rlc*v?jtfxzs1IunoyJTCeawkhZVXUPSAqpdbGOEKmD%#H8RWMNB0Q&@',fineEdge:.35,blockOff:.06,
    details:{standard:{columns:200,sub:[1,1]},fine:{columns:320,sub:[1,1]},blocks:{columns:240,sub:[1,2]},braille:{columns:200,sub:[2,4]}}};
  const asciiDetail=detail=>{
    if(typeof detail!=='string'||!Object.prototype.hasOwnProperty.call(ASCII.details,detail))throw Error('ASCII detail must be standard, fine, blocks or braille');
    return ASCII.details[detail];
  };
  const asciiGrid=(width,height,detail='standard')=>{
    const columns=detail==='standard'?ASCII.columns:asciiDetail(detail).columns;
    return {columns,rows:Math.max(1,Math.round(columns*height/width/ASCII.cellAspect))};
  };
  // Brightness 0..1 to a ramp index. Monotonic: a brighter cell never gets a sparser glyph.
  const asciiLevel=(lum,ramp=ASCII.ramp)=>Math.round(Math.pow(clamp(lum,0,1),ASCII.gamma)*(ramp.length-1));
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
  // Toned luminance of n RGBA samples, and its Sobel gradient on a w x h sample grid.
  function asciiLuma(pixels,n){
    const lum=new Float32Array(n);
    for(let i=0;i<n;i++)lum[i]=(pixels[i*4]*.2126+pixels[i*4+1]*.7152+pixels[i*4+2]*.0722)/255;
    const tone=asciiTone(lum);for(let i=0;i<n;i++)lum[i]=tone(lum[i]);
    return lum;
  }
  function asciiSobel(lum,w,h){
    const n=w*h,mag=new Float32Array(n),gxs=new Float32Array(n),gys=new Float32Array(n);
    const at=(x,y)=>lum[clamp(y,0,h-1)*w+clamp(x,0,w-1)];
    for(let y=0;y<h;y++)for(let x=0;x<w;x++){
      const i=y*w+x;
      gxs[i]=at(x+1,y-1)+2*at(x+1,y)+at(x+1,y+1)-at(x-1,y-1)-2*at(x-1,y)-at(x-1,y+1);
      gys[i]=at(x-1,y+1)+2*at(x,y+1)+at(x+1,y+1)-at(x-1,y-1)-2*at(x,y-1)-at(x+1,y-1);
      mag[i]=Math.hypot(gxs[i],gys[i]);
    }
    return {mag,gxs,gys,at};
  }
  // Glyph colour from one RGBA sample: glyph density already carries brightness, so lift the colour so dark hues
  // stay legible on the dark ground.
  function asciiLift(pixels,k,colors,o){
    const r=pixels[k*4],g=pixels[k*4+1],b=pixels[k*4+2],peak=Math.max(r,g,b)/255;
    const gain=peak>0?Math.max(ASCII.floor,Math.pow(peak,ASCII.lift))/peak:0;
    colors[o]=Math.round(r*gain);colors[o+1]=Math.round(g*gain);colors[o+2]=Math.round(b*gain);
  }
  // Pure: RGBA pixels at the detail's samples per cell -> glyphs and glyph colours. No canvas, clock or random input.
  // options.detail: 'standard' (default, unchanged), 'fine', 'blocks' or 'braille'. Pixels are columns*sub[0] wide
  // and rows*sub[1] high for the chosen detail.
  function asciiCells(pixels,columns,rows,mode='color',options){
    if(mode!=='color'&&mode!=='mono')throw Error('ASCII mode must be color or mono');
    const detail=options&&options.detail!==undefined?options.detail:'standard',[ux,uy]=asciiDetail(detail).sub;
    const n=columns*rows;if(pixels.length<n*ux*uy*4)throw Error('ASCII pixels do not cover the grid');
    if(detail==='blocks')return asciiBlocks(pixels,columns,rows,mode);
    if(detail==='braille')return asciiBraille(pixels,columns,rows,mode);
    const fine=detail==='fine',ramp=fine?ASCII.richRamp:ASCII.ramp,threshold=fine?ASCII.fineEdge:ASCII.edge;
    const lum=asciiLuma(pixels,n),{mag,gxs,gys,at}=asciiSobel(lum,columns,rows),chars=new Array(n),colors=new Uint8ClampedArray(n*3);
    const strength=(x,y)=>x<0||y<0||x>=columns||y>=rows?0:mag[y*columns+x];
    let edges=0;
    for(let y=0;y<rows;y++)for(let x=0;x<columns;x++){
      const i=y*columns+x;let glyph=ramp[asciiLevel(lum[i],ramp)],source=i;
      if(mag[i]>=threshold){
        // One glyph per crossing, on the darker side of the step, so a bright shape keeps its fill and gains an outline.
        let sx=Math.round(gxs[i]/mag[i]),sy=Math.round(gys[i]/mag[i]);
        const turn=(Math.atan2(gys[i],gxs[i])*180/Math.PI+180)%180,flat=turn>=67.5&&turn<112.5;
        // Fine detail: a horizontal step is claimed by the cell above it, whose baseline lies on the step ('_'),
        // so the tops and bottoms of a silhouette both close cleanly.
        if(fine&&flat&&sy<0){sx=-sx;sy=-sy}
        if(mag[i]>strength(x-sx,y-sy)&&mag[i]>=strength(x+sx,y+sy)){
          const low=fine&&flat&&Math.abs(at(x,y+1)-at(x,y))>=Math.abs(at(x,y)-at(x,y-1));
          glyph=turn<22.5||turn>=157.5?'|':turn<67.5?'/':turn<112.5?(low?'_':'-'):'\\';edges++;
          // Fine detail colours an outline with the lit side of its step, so it reads against the dark ground.
          if(fine){const j=clamp(y+sy,0,rows-1)*columns+clamp(x+sx,0,columns-1);if(lum[j]>lum[i])source=j}
        }
      }
      chars[i]=glyph;
      if(mode==='mono'){colors[i*3]=ASCII.mono[0];colors[i*3+1]=ASCII.mono[1];colors[i*3+2]=ASCII.mono[2]}
      else asciiLift(pixels,source,colors,i*3);
    }
    const out={columns,rows,mode,chars:chars.join(''),colors,edges};
    if(fine)out.detail='fine';
    return out;
  }
  // Half blocks: each cell holds an upper and a lower sample. A lit half is drawn in its own colour; unlit halves
  // stay ground. Colour mode keeps the scene hue at the toned brightness, mono uses neutral grey levels.
  function asciiBlocks(pixels,columns,rows,mode){
    const n=columns*rows,lum=asciiLuma(pixels,n*2),chars=new Array(n),colors=new Uint8ClampedArray(n*3),background=new Uint8ClampedArray(n*3);
    const shade=(k,out,o)=>{
      if(mode==='mono'){for(let c=0;c<3;c++)out[o+c]=Math.round(ASCII.mono[c]*lum[k]);return}
      // Scale to the toned brightness, but never past full scale on any channel, so the hue survives.
      const r=pixels[k*4],g=pixels[k*4+1],b=pixels[k*4+2],raw=(r*.2126+g*.7152+b*.0722)/255,gain=raw>0?Math.min(lum[k]/raw,255/Math.max(r,g,b)):0;
      out[o]=Math.round(r*gain);out[o+1]=Math.round(g*gain);out[o+2]=Math.round(b*gain);
    };
    for(let y=0;y<rows;y++)for(let x=0;x<columns;x++){
      const i=y*columns+x,top=2*y*columns+x,bottom=top+columns,a=lum[top]>=ASCII.blockOff,b=lum[bottom]>=ASCII.blockOff;
      if(!a&&!b){chars[i]=' ';continue}
      if(a&&b){
        shade(top,colors,i*3);shade(bottom,background,i*3);
        const same=colors[i*3]===background[i*3]&&colors[i*3+1]===background[i*3+1]&&colors[i*3+2]===background[i*3+2];
        chars[i]=same?'█':'▀';if(same)background.fill(0,i*3,i*3+3);
      }else if(a){chars[i]='▀';shade(top,colors,i*3)}
      else{chars[i]='▄';shade(bottom,colors,i*3)}
    }
    return {columns,rows,mode,detail:'blocks',chars:chars.join(''),colors,background,edges:0};
  }
  // Braille: a 2x4 dot matrix per cell. A dot is raised by an ordered threshold, so midtones keep their density,
  // and on the bright side of any strong step, so an outline stays unbroken even in a mid-grey shape.
  const BRAILLE_BITS=[[0x01,0x08],[0x02,0x10],[0x04,0x20],[0x40,0x80]],BRAILLE_ORDER=[[0,4],[6,2],[1,5],[7,3]];
  function asciiBraille(pixels,columns,rows,mode){
    const w=columns*2,h=rows*4,n=columns*rows,lum=asciiLuma(pixels,w*h),{mag,at}=asciiSobel(lum,w,h);
    const chars=new Array(n),colors=new Uint8ClampedArray(n*3);let edges=0;
    for(let y=0;y<rows;y++)for(let x=0;x<columns;x++){
      const i=y*columns+x;let bits=0,brightest=-1,source=-1;
      for(let v=0;v<4;v++)for(let u=0;u<2;u++){
        const px=x*2+u,py=y*4+v,k=py*w+px,l=lum[k];if(l<ASCII.blockOff)continue;
        let lit=l>(BRAILLE_ORDER[v][u]+.5)/8;
        if(!lit&&mag[k]>=ASCII.fineEdge){
          let mean=0;for(let dy=-1;dy<=1;dy++)for(let dx=-1;dx<=1;dx++)mean+=at(px+dx,py+dy);
          if(l>=mean/9){lit=true;edges++}
        }
        if(lit){bits|=BRAILLE_BITS[v][u];if(l>brightest){brightest=l;source=k}}
      }
      chars[i]=bits?String.fromCharCode(0x2800+bits):' ';
      if(!bits)continue;
      if(mode==='mono'){colors[i*3]=ASCII.mono[0];colors[i*3+1]=ASCII.mono[1];colors[i*3+2]=ASCII.mono[2]}
      else asciiLift(pixels,source,colors,i*3);
    }
    return {columns,rows,mode,detail:'braille',chars:chars.join(''),colors,edges};
  }
  let asciiSampler=null;
  // options.detail as for asciiCells; omitted, the view is exactly the standard one.
  function renderAscii(ctx,scratch,mode='color',options){
    const detail=options&&options.detail!==undefined?options.detail:'standard',[ux,uy]=asciiDetail(detail).sub;
    const W=ctx.canvas.width,H=ctx.canvas.height,{columns,rows}=asciiGrid(W,H,detail),sw=columns*ux*ASCII.sample,sh=rows*uy*ASCII.sample;
    if(!asciiSampler||asciiSampler.width!==sw||asciiSampler.height!==sh){asciiSampler=document.createElement('canvas');asciiSampler.width=sw;asciiSampler.height=sh}
    const s=asciiSampler.getContext('2d',{willReadFrequently:true});s.imageSmoothingEnabled=true;s.imageSmoothingQuality='high';s.drawImage(scratch,0,0,sw,sh);
    const pixels=asciiReduce(s.getImageData(0,0,sw,sh).data,sw,sh,ASCII.sample);
    const grid=detail==='standard'?asciiCells(pixels,columns,rows,mode):asciiCells(pixels,columns,rows,mode,{detail}),cw=W/columns,ch=H/rows;
    ctx.save();ctx.setTransform(1,0,0,1,0,0);ctx.globalAlpha=1;ctx.globalCompositeOperation='source-over';
    ctx.fillStyle=mode==='mono'?'#000':'#05080a';ctx.fillRect(0,0,W,H);
    let last=-1;
    const paint=(colors,i)=>{
      const key=colors[i*3]<<16|colors[i*3+1]<<8|colors[i*3+2];
      if(key!==last){ctx.fillStyle=`rgb(${colors[i*3]},${colors[i*3+1]},${colors[i*3+2]})`;last=key}
    };
    if(detail==='blocks'){
      // Half blocks are drawn as exact rectangles, so adjacent cells meet without font gaps.
      for(let y=0;y<rows;y++){
        const y0=Math.round(y*ch),ym=Math.round((y+.5)*ch),y1=Math.round((y+1)*ch);
        for(let x=0;x<columns;x++){
          const i=y*columns+x,glyph=grid.chars[i];if(glyph===' ')continue;
          const x0=Math.round(x*cw),x1=Math.round((x+1)*cw);
          paint(grid.colors,i);
          if(glyph==='█')ctx.fillRect(x0,y0,x1-x0,y1-y0);
          else if(glyph==='▀')ctx.fillRect(x0,y0,x1-x0,ym-y0);
          else ctx.fillRect(x0,ym,x1-x0,y1-ym);
          if(glyph==='▀'&&(grid.background[i*3]||grid.background[i*3+1]||grid.background[i*3+2])){paint(grid.background,i);ctx.fillRect(x0,ym,x1-x0,y1-ym)}
        }
      }
    }else if(detail==='braille'){
      // Each raised dot is drawn where the braille glyph places it, independent of which fonts are installed.
      const dot=Math.max(1,Math.min(cw/2,ch/4)*.78);
      for(let y=0;y<rows;y++)for(let x=0;x<columns;x++){
        const i=y*columns+x,glyph=grid.chars[i];if(glyph===' ')continue;
        const bits=glyph.charCodeAt(0)-0x2800;paint(grid.colors,i);
        for(let v=0;v<4;v++)for(let u=0;u<2;u++)if(bits&BRAILLE_BITS[v][u])ctx.fillRect((x+(u+.5)/2)*cw-dot/2,(y+(v+.5)/4)*ch-dot/2,dot,dot);
      }
    }else{
      ctx.font=`bold ${(ch*1.08).toFixed(2)}px Consolas,"Cascadia Mono",Menlo,"DejaVu Sans Mono","Liberation Mono",monospace`;ctx.textAlign='center';ctx.textBaseline='middle';
      for(let y=0;y<rows;y++)for(let x=0;x<columns;x++){
        const i=y*columns+x,glyph=grid.chars[i];if(glyph===' ')continue;
        paint(grid.colors,i);
        ctx.fillText(glyph,(x+.5)*cw,(y+.5)*ch);
      }
    }
    ctx.restore();
  }
  const api={pose,trackAt,fragmentPose,renderScene,renderAscii,asciiCells,asciiGrid,asciiLevel,asciiReduce,asciiTone,asciiDetail,ASCII};if(typeof module!=='undefined')module.exports=api;else root.RekindraScene=api;
})(globalThis);
