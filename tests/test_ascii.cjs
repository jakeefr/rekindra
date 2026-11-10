const test=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs'),path=require('node:path');
const {asciiCells,asciiGrid,asciiLevel,asciiReduce,asciiTone,ASCII}=require('../runtime/scene.js');

// Grid-resolution RGBA frame from a colour function; no canvas involved.
function frame(columns,rows,color){
  const pixels=new Uint8ClampedArray(columns*rows*4);
  for(let y=0;y<rows;y++)for(let x=0;x<columns;x++){const [r,g,b]=color(x,y);pixels.set([r,g,b,255],(y*columns+x)*4)}
  return pixels;
}
// A fixed integer pattern with gradients and steps, standing in for a rendered frame.
const pattern=(x,y)=>[(x*7+y*3)%256,(x*x+y*11)%256,(x*5^y*13)%256];

test('the grid is dense and matches the frame shape',()=>{
  const grid=asciiGrid(1280,720);
  assert.deepEqual(grid,{columns:200,rows:60});
  assert.ok(grid.columns>=180);
  // Each cell is drawn ASCII.cellAspect times taller than wide, so the picture is not stretched.
  assert.ok(Math.abs((720/grid.rows)/(1280/grid.columns)-ASCII.cellAspect)<.01);
  assert.equal(asciiGrid(720,1280).columns,200);assert.ok(asciiGrid(720,1280).rows>asciiGrid(1280,720).rows);
  const cells=asciiCells(frame(200,60,pattern),200,60);
  assert.equal(cells.columns,200);assert.equal(cells.rows,60);
  assert.equal(cells.chars.length,200*60);assert.equal(cells.colors.length,200*60*3);
});

test('the same pixels always give the same characters and colours',()=>{
  for(const mode of ['color','mono']){
    const a=asciiCells(frame(200,60,pattern),200,60,mode),b=asciiCells(frame(200,60,pattern),200,60,mode);
    assert.equal(a.chars,b.chars);assert.deepEqual(a.colors,b.colors);assert.equal(a.edges,b.edges);
  }
  const source=fs.readFileSync(path.join(__dirname,'../runtime/scene.js'),'utf8');
  const view=source.slice(source.indexOf('// ASCII view'),source.indexOf('const api='));
  assert.ok(view.length>500);
  assert.doesNotMatch(view,/Math\.random|Date\b|performance\.|requestAnimationFrame/);
});

test('the ramp is fixed, distinct and monotonic in brightness',()=>{
  assert.ok(ASCII.ramp.length>=24);
  assert.equal(new Set(ASCII.ramp).size,ASCII.ramp.length);
  assert.equal(ASCII.ramp[0],' ');
  for(const edgeGlyph of '|/-\\')assert.equal(ASCII.ramp.includes(edgeGlyph),false);
  assert.equal(asciiLevel(0),0);assert.equal(asciiLevel(1),ASCII.ramp.length-1);
  let previous=0;const used=new Set();
  for(let v=0;v<=255;v++){
    const level=asciiLevel(v/255);assert.ok(level>=previous,'brighter input chose a sparser glyph');previous=level;used.add(level);
    // A flat grey field has no edges, so the whole grid is that level's glyph.
    const cells=asciiCells(frame(8,6,()=>[v,v,v]),8,6,'mono');
    assert.equal(cells.chars,ASCII.ramp[level].repeat(48));assert.equal(cells.edges,0);
  }
  assert.equal(used.size,ASCII.ramp.length,'every ramp glyph is reachable');
});

test('color mode carries the scene colour and mono mode does not',()=>{
  const halves=(x)=>x<10?[200,40,30]:[30,60,210];
  const color=asciiCells(frame(20,6,halves),20,6,'color'),mono=asciiCells(frame(20,6,halves),20,6,'mono');
  assert.equal(color.chars,mono.chars,'mode changes colour only, never the characters');
  const at=(cells,x,y)=>Array.from(cells.colors.slice((y*20+x)*3,(y*20+x)*3+3));
  const red=at(color,2,3),blue=at(color,17,3);
  assert.ok(red[0]>red[1]&&red[0]>red[2]);assert.ok(blue[2]>blue[0]&&blue[2]>blue[1]);
  // Hue is preserved: channel ratios match the source within rounding.
  assert.ok(Math.abs(red[1]/red[0]-40/200)<.02&&Math.abs(blue[0]/blue[2]-30/210)<.02);
  for(let i=0;i<20*6;i++)assert.deepEqual(Array.from(mono.colors.slice(i*3,i*3+3)),ASCII.mono);
  assert.equal(new Set(ASCII.mono).size<=2&&Math.max(...ASCII.mono)-Math.min(...ASCII.mono)<8,true,'mono foreground is neutral');
  // A dark hue is lifted enough to stay legible, and never past full scale.
  const dark=asciiCells(frame(4,4,()=>[10,20,40]),4,4,'color');
  assert.ok(Math.max(...dark.colors)>=Math.floor(255*ASCII.floor)&&Math.max(...dark.colors)<=255);
  assert.deepEqual(Array.from(asciiCells(frame(4,4,()=>[0,0,0]),4,4,'color').colors),new Array(48).fill(0));
  assert.throws(()=>asciiCells(frame(4,4,pattern),4,4,'sepia'),/color or mono/);
  assert.throws(()=>asciiCells(new Uint8ClampedArray(8),4,4),/cover the grid/);
});

test('strong edges become one directional glyph on the darker side',()=>{
  const row=(cells,y)=>cells.chars.slice(y*cells.columns,(y+1)*cells.columns);
  // Vertical step: dark left, bright right.
  const vertical=asciiCells(frame(20,10,x=>x<10?[20,20,20]:[230,230,230]),20,10,'mono');
  for(let y=0;y<10;y++){
    const line=row(vertical,y);
    assert.equal(line[9],'|');assert.equal(line.split('|').length,2,'one outline glyph per crossing');
    assert.equal(line[10],'@','the bright side keeps its fill');assert.equal(line[0],' ');
  }
  // Horizontal step.
  const horizontal=asciiCells(frame(20,10,(x,y)=>y<5?[230,230,230]:[20,20,20]),20,10,'mono');
  assert.equal(row(horizontal,5),'-'.repeat(20));assert.equal(row(horizontal,4).includes('-'),false);
  // Diagonals: bright below a line rising to the right reads '/', the mirror reads '\'.
  const rising=asciiCells(frame(20,20,(x,y)=>x+y>20?[230,230,230]:[20,20,20]),20,20,'mono');
  const falling=asciiCells(frame(20,20,(x,y)=>y-x>0?[230,230,230]:[20,20,20]),20,20,'mono');
  assert.ok(rising.chars.includes('/')&&!rising.chars.includes('\\'));
  assert.ok(falling.chars.includes('\\')&&!falling.chars.includes('/'));
  // A weak step stays plain shading.
  const weak=asciiCells(frame(20,10,x=>x<10?[100,100,100]:[108,108,108]),20,10,'mono');
  assert.equal(weak.edges,0);assert.doesNotMatch(weak.chars,/[|\/\\-]/);
});

test('frame contrast is bounded, increasing and leaves a flat frame alone',()=>{
  const flat=asciiTone(new Float32Array(100).fill(.4));
  assert.equal(flat(.4),.4);
  // A full-range frame is not changed beyond clipping its extreme few percent.
  const full=asciiTone(Float32Array.from({length:256},(_,i)=>i/255));
  assert.ok(Math.abs(full(.5)-.5)<.01);
  // A narrow frame is spread by at most ASCII.gain, about its own middle.
  const narrow=asciiTone(Float32Array.from({length:200},(_,i)=>.4+.1*i/199));
  assert.ok(Math.abs((narrow(.5)-narrow(.4))/.1-ASCII.gain)<.2);
  assert.ok(Math.abs(narrow(.45)-.45)<.02);
  for(const tone of [flat,full,narrow]){let previous=-1;for(let v=0;v<=255;v++){const out=tone(v/255);assert.ok(out>=previous&&out>=0&&out<=1);previous=out}}
  // In a whole frame, a brighter cell never gets a sparser shading glyph.
  const ramp=asciiCells(frame(64,4,x=>[x*4,x*4,x*4]),64,4,'mono').chars.slice(64,128);
  let last=0;for(const glyph of ramp){const level=ASCII.ramp.indexOf(glyph);if(level<0)continue;assert.ok(level>=last);last=level}
  assert.equal(ramp[0],' ');assert.equal(ramp[63],'@');
});

// renderAscii against a recording 2D context; the sampler returns the fixed pattern at whatever size it is asked for.
function recordRender(mode,options){
  const {renderAscii}=require('../runtime/scene.js'),log=[],saved=global.document;
  global.document={createElement:()=>({width:0,height:0,getContext:()=>({drawImage(){},getImageData:(x,y,w,h)=>({data:frame(w,h,pattern)})})})};
  const ctx=new Proxy({canvas:{width:1280,height:720}},{get(t,k){return k==='canvas'?t.canvas:(...a)=>log.push([k,...a])},set(t,k,v){log.push(['set',k,v]);return true}});
  try{if(options===undefined)renderAscii(ctx,{},mode);else renderAscii(ctx,{},mode,options)}finally{global.document=saved}
  return log;
}
const sha=s=>require('node:crypto').createHash('sha256').update(s).digest('hex');

test('the default view is byte-identical to the view before detail levels existed',()=>{
  // Hashes captured from the runtime before the detail option was added.
  const before={
    'cells-color':'11f758c86eea134d7d2af94fdeb0fc320b44ffddae48a91137ccb1f0a0d890d8',
    'cells-mono':'a6baaf9c61779964f7bf3c268481428ef889dc1fb8611bf32f1ef338a7d393db',
    'render-color':'3a66e0be80443e6f2aca5eed07f7c7bc03e107dceba6571ffbe494d58eea6b53',
    'render-mono':'71e2f90b766c3c4df6ee756c8a9b2b74ce692edfe426e3cbf544b21e6ff31fc2'};
  for(const mode of ['color','mono']){
    for(const options of [undefined,{detail:'standard'},{}]){
      const c=asciiCells(frame(200,60,pattern),200,60,mode,options);
      assert.equal(sha(c.chars+'|'+Buffer.from(c.colors).toString('hex')+'|'+c.edges),before['cells-'+mode]);
      assert.equal(sha(JSON.stringify(recordRender(mode,options))),before['render-'+mode]);
    }
  }
});

// A figure on a dark ground: round head over an oval body, two raised triangular wings. Coordinates in a 1280x720 frame.
function inside(px,py,a,b,c){const s=(p,q,r)=>(p[0]-r[0])*(q[1]-r[1])-(q[0]-r[0])*(p[1]-r[1]);const d=[s([px,py],a,b),s([px,py],b,c),s([px,py],c,a)];return !(d.some(v=>v<0)&&d.some(v=>v>0))}
function figurePart(px,py){
  if(Math.hypot(px-640,py-230)<60)return 'head';
  if(((px-640)/90)**2+((py-450)/150)**2<1)return 'body';
  if(inside(px,py,[560,380],[300,110],[430,470]))return 'left';
  if(inside(px,py,[720,380],[980,110],[850,470]))return 'right';
  return null;
}
const partColor={head:[230,200,170],body:[200,150,90],left:[120,170,230],right:[120,170,230]};
function figureFrame(detail){
  const {columns,rows}=asciiGrid(1280,720,detail),[ux,uy]=ASCII.details[detail].sub,w=columns*ux,h=rows*uy;
  const part=(x,y)=>figurePart((x+.5)/w*1280,(y+.5)/h*720);
  return {columns,rows,w,h,part,pixels:frame(w,h,(x,y)=>partColor[part(x,y)]||[10,12,16])};
}

test('detail levels: a finer grid, the same cell shape, and a clear error for an unknown level',()=>{
  const standard=asciiGrid(1280,720),fine=asciiGrid(1280,720,'fine');
  assert.ok(fine.columns>=300&&fine.columns>standard.columns&&fine.rows>standard.rows);
  for(const detail of Object.keys(ASCII.details)){
    const grid=asciiGrid(1280,720,detail);
    assert.ok(Math.abs((720/grid.rows)/(1280/grid.columns)-ASCII.cellAspect)<.03,detail);
  }
  assert.throws(()=>asciiGrid(1280,720,'ultra'),/standard, fine, blocks or braille/);
  assert.throws(()=>asciiCells(frame(4,4,pattern),4,4,'mono',{detail:'toString'}),/standard, fine, blocks or braille/);
  assert.throws(()=>asciiCells(frame(4,4,pattern),4,4,'mono',{detail:'braille'}),/cover the grid/);
});

test('the rich ramp is long, distinct, free of outline glyphs and monotonic',()=>{
  const ramp=ASCII.richRamp;
  assert.ok(ramp.length>=60&&ramp.length<=72,`rich ramp has ${ramp.length} glyphs`);
  assert.equal(new Set(ramp).size,ramp.length);assert.equal(ramp[0],' ');
  for(const edgeGlyph of '|/-\\_')assert.equal(ramp.includes(edgeGlyph),false);
  let previous=0;const used=new Set();
  for(let v=0;v<=255;v++){const level=asciiLevel(v/255,ramp);assert.ok(level>=previous);previous=level;used.add(level)}
  assert.equal(used.size,ramp.length,'every rich ramp glyph is reachable');
  const flat=asciiCells(frame(8,6,()=>[128,128,128]),8,6,'mono',{detail:'fine'});
  assert.equal(flat.chars,ramp[asciiLevel(128/255,ramp)].repeat(48));assert.equal(flat.edges,0);
});

test('fine detail closes horizontal steps with an underscore on the cell above the step',()=>{
  const row=(cells,y)=>cells.chars.slice(y*cells.columns,(y+1)*cells.columns);
  // Bright above dark (the bottom of a shape): the last bright row carries the line.
  const bottom=asciiCells(frame(20,10,(x,y)=>y<5?[230,230,230]:[20,20,20]),20,10,'mono',{detail:'fine'});
  assert.equal(row(bottom,4),'_'.repeat(20));assert.equal(row(bottom,5).trim(),'');
  // Dark above bright (the top of a shape): the last dark row carries it, so the line sits on the step.
  const top=asciiCells(frame(20,10,(x,y)=>y<5?[20,20,20]:[230,230,230]),20,10,'mono',{detail:'fine'});
  assert.equal(row(top,4),'_'.repeat(20));assert.equal(row(top,5),'@'.repeat(20));
  // Vertical and diagonal steps keep their directional glyphs.
  const vertical=asciiCells(frame(20,10,x=>x<10?[20,20,20]:[230,230,230]),20,10,'mono',{detail:'fine'});
  for(let y=0;y<10;y++)assert.equal(row(vertical,y)[9],'|');
  const rising=asciiCells(frame(20,20,(x,y)=>x+y>20?[230,230,230]:[20,20,20]),20,20,'mono',{detail:'fine'});
  assert.ok(rising.chars.includes('/')&&!rising.chars.includes('\\'));
  // Fine detail outlines a step too weak for the standard view. Black and white rows pin the frame's range,
  // so frame contrast does not amplify the step.
  const soft=(x,y)=>y===0?[0,0,0]:y===9?[255,255,255]:x<10?[100,100,100]:[130,130,130];
  const middle=cells=>[3,4,5,6].map(y=>row(cells,y)[9]).join('');
  assert.equal(middle(asciiCells(frame(20,10,soft),20,10,'mono')).match(/[|\/\\_-]/),null);
  assert.equal(middle(asciiCells(frame(20,10,soft),20,10,'mono',{detail:'fine'})),'||||');
});

test('fine detail outlines a head and raised wings in colour and in black and white',()=>{
  const {columns,rows,part,pixels}=figureFrame('fine');
  const color=asciiCells(pixels,columns,rows,'color',{detail:'fine'}),mono=asciiCells(pixels,columns,rows,'mono',{detail:'fine'});
  assert.equal(color.chars,mono.chars,'mode changes colour only');
  const at=(x,y)=>color.chars[y*columns+x],edge=g=>'|/\\-_'.includes(g);
  const boundary=(x,y)=>[[1,0],[-1,0],[0,1],[0,-1]].some(([dx,dy])=>x+dx>=0&&y+dy>=0&&x+dx<columns&&y+dy<rows&&!!part(x+dx,y+dy)!==!!part(x,y));
  const near=(x,y,test)=>{for(let dy=-1;dy<=1;dy++)for(let dx=-1;dx<=1;dx++){const u=x+dx,v=y+dy;if(u>=0&&v>=0&&u<columns&&v<rows&&test(u,v))return true}return false};
  let border=0,outlined=0;const kinds=new Set(),wings={left:0,right:0};
  for(let y=0;y<rows;y++)for(let x=0;x<columns;x++){
    if(edge(at(x,y))){
      kinds.add(at(x,y));
      assert.ok(near(x,y,boundary),`outline glyph off the silhouette at ${x},${y}`);
      const p=near(x,y,(u,v)=>part(u,v)==='left')?'left':near(x,y,(u,v)=>part(u,v)==='right')?'right':null;if(p&&y<rows*.3)wings[p]++;
    }
    // Only the outer silhouette: wing/body/head contacts share a colour step but are not the figure's outline.
    if(boundary(x,y)&&!part(x,y)){border++;if(near(x,y,(u,v)=>edge(at(u,v))))outlined++}
  }
  assert.ok(outlined/border>=.95,`outline covers ${(100*outlined/border).toFixed(1)}% of the silhouette`);
  for(const glyph of '_/\\|')assert.ok(kinds.has(glyph),`missing ${glyph} on the silhouette`);
  // The raised wing tips are outlined on both sides, above the head.
  assert.ok(wings.left>=10&&wings.right>=10,JSON.stringify(wings));
  // The top of the head is a run of underscores.
  const headTop=Math.floor((170/720)*rows)-1;
  assert.ok(/_{6,}/.test(color.chars.slice(headTop*columns,(headTop+2)*columns)),'head top is not closed');
  // In colour the outline takes the lit side's hue, not the ground's.
  let lit=0,count=0;
  for(let i=0;i<columns*rows;i++)if(edge(color.chars[i])){count++;if(Math.max(color.colors[i*3],color.colors[i*3+1],color.colors[i*3+2])>150)lit++}
  assert.ok(lit/count>.9);
  for(let i=0;i<columns*rows;i++)assert.deepEqual(Array.from(mono.colors.slice(i*3,i*3+3)),ASCII.mono);
});

test('half blocks follow the silhouette at two samples per cell in colour and in black and white',()=>{
  const {columns,rows,part,pixels}=figureFrame('blocks');
  for(const mode of ['color','mono']){
    const cells=asciiCells(pixels,columns,rows,mode,{detail:'blocks'});
    assert.equal(cells.chars.length,columns*rows);assert.match(cells.chars,/^[ ▀▄█]+$/);
    for(const g of '▀▄█')assert.ok(cells.chars.includes(g),`no ${g} cells`);
    for(let y=0;y<rows;y++)for(let x=0;x<columns;x++){
      const g=cells.chars[y*columns+x],top=!!part(x,2*y),bottom=!!part(x,2*y+1);
      const shownTop=g==='█'||g==='▀',shownBottom=g==='█'||g==='▄'||(g==='▀'&&cells.background.slice((y*columns+x)*3,(y*columns+x)*3+3).some(v=>v>0));
      assert.equal(shownTop,top,`${mode} top half at ${x},${y}`);assert.equal(shownBottom,bottom,`${mode} bottom half at ${x},${y}`);
    }
    const wing=Math.round(columns*.31)+Math.round(rows*.5)*columns,c=Array.from(cells.colors.slice(wing*3,wing*3+3));
    assert.equal(part(Math.round(columns*.31),2*Math.round(rows*.5)),'left');
    if(mode==='color')assert.ok(c[2]>c[0]&&c[2]>c[1],'wing keeps its blue');
    else assert.ok(Math.max(...c)-Math.min(...c)<8&&c[0]>100,'black and white is neutral grey');
  }
});

test('braille raises dots only on the figure and outlines it at 2x4 dots per cell',()=>{
  const {columns,rows,w,part,pixels}=figureFrame('braille');
  const color=asciiCells(pixels,columns,rows,'color',{detail:'braille'}),mono=asciiCells(pixels,columns,rows,'mono',{detail:'braille'});
  assert.equal(color.chars,mono.chars);assert.match(color.chars,/^[ ⠁-⣿]+$/);
  const bits=[[0x01,0x08],[0x02,0x10],[0x04,0x20],[0x40,0x80]];
  let figure=0,raised=0,stray=0;
  for(let y=0;y<rows;y++)for(let x=0;x<columns;x++){
    const g=color.chars[y*columns+x],b=g===' '?0:g.charCodeAt(0)-0x2800;
    for(let v=0;v<4;v++)for(let u=0;u<2;u++){const on=!!(b&bits[v][u]),inFigure=!!part(x*2+u,y*4+v);if(inFigure){figure++;if(on)raised++}else if(on)stray++}
  }
  assert.equal(stray,0,'no dots on the ground');assert.ok(raised/figure>.9,`${(100*raised/figure).toFixed(1)}% of figure dots raised`);
  assert.ok(new Set(color.chars).size>20,'partial cells along the outline use many dot patterns');
  // A mid-grey figure is dithered inside but its outline stays unbroken.
  const grey=frame(w,rows*4,(x,y)=>part(x,y)?[90,90,90]:[10,12,16]);
  const flat=asciiCells(grey,columns,rows,'mono',{detail:'braille'});
  let rim=0,rimOn=0;
  for(let y=1;y<rows*4-1;y++)for(let x=1;x<w-1;x++){
    if(!part(x,y)||[[1,0],[-1,0],[0,1],[0,-1]].every(([dx,dy])=>part(x+dx,y+dy)))continue;
    const cx=x>>1,cy=y>>2,g=flat.chars[cy*columns+cx],b=g===' '?0:g.charCodeAt(0)-0x2800;rim++;if(b&bits[y&3][x&1])rimOn++;
  }
  assert.ok(rimOn/rim>.85,`${(100*rimOn/rim).toFixed(1)}% of the grey outline raised`);
  // Colour mode colours each cell from its lit dots; black and white stays neutral.
  const i=color.chars.indexOf('⣿');assert.ok(i>=0&&Math.max(...color.colors.slice(i*3,i*3+3))>150);
  assert.deepEqual(Array.from(mono.colors.slice(i*3,i*3+3)),ASCII.mono);
});

test('detailed views render through the same canvas path',()=>{
  for(const detail of ['fine','blocks','braille'])for(const mode of ['color','mono']){
    const log=recordRender(mode,{detail}),draws=log.filter(([k])=>k==='fillText'||k==='fillRect');
    assert.ok(draws.length>1000,`${detail} ${mode} drew ${draws.length}`);
    if(detail!=='fine')assert.equal(log.some(([k])=>k==='fillText'),false);
    assert.equal(log[log.length-1][0],'restore');
  }
});

test('block averaging keeps a thin shape that point sampling would drop',()=>{
  // A one-pixel bright column in a 2x supersampled frame survives as a half-bright cell.
  const wide=frame(8,4,x=>x===3?[255,255,255]:[0,0,0]),reduced=asciiReduce(wide,8,4,2);
  assert.equal(reduced.length,4*2*4);
  assert.deepEqual(Array.from(reduced.slice(4,8)),[128,128,128,255]);
  assert.deepEqual(Array.from(reduced.slice(0,4)),[0,0,0,255]);
});
