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

test('block averaging keeps a thin shape that point sampling would drop',()=>{
  // A one-pixel bright column in a 2x supersampled frame survives as a half-bright cell.
  const wide=frame(8,4,x=>x===3?[255,255,255]:[0,0,0]),reduced=asciiReduce(wide,8,4,2);
  assert.equal(reduced.length,4*2*4);
  assert.deepEqual(Array.from(reduced.slice(4,8)),[128,128,128,255]);
  assert.deepEqual(Array.from(reduced.slice(0,4)),[0,0,0,255]);
});
