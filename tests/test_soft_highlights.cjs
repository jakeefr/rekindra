const test=require('node:test'),assert=require('node:assert/strict');
const {softHighlight,softTone}=require('../runtime/world.js');
const standard=x=>(1-Math.exp(-Math.max(x,0)))**(1/2.2);
test('soft highlights follow the standard curve below the knee',()=>{
  for(const x of [0,.01,.1,.5,1,1.5,Math.log(5)-1e-9])assert.ok(Math.abs(softHighlight(x)-standard(x))<1e-12,x);
  assert.equal(softHighlight(-3),0);
});
test('soft highlights rise monotonically and never reach white',()=>{
  let last=-1;
  for(let x=0;x<=400;x+=.01){const y=softHighlight(x);assert.ok(y>last,`not rising at ${x}`);assert.ok(y<1,`reached white at ${x}`);last=y}
  for(const x of [1e3,1e6,1e9])assert.ok(softHighlight(x)<1,x);
  // The shoulder keeps visible gradient where the standard curve has already clipped to 8-bit white.
  assert.equal(Math.round(standard(8)*255),255);assert.ok(Math.round(softHighlight(8)*255)<255);
  assert.ok(Math.round(softHighlight(40)*255)>Math.round(softHighlight(8)*255));
});
test('the shoulder joins the standard curve without a jump in slope',()=>{
  const k=Math.log(5),h=1e-6,pre=x=>softHighlight(x)**2.2;
  const below=(pre(k)-pre(k-h))/h,above=(pre(k+h)-pre(k))/h;
  assert.ok(Math.abs(below-above)<1e-4,`${below} vs ${above}`);
});
test('the GLSL form names only its input and the exposure uniform',()=>{
  const glsl=softTone('L');
  assert.match(glsl,/^pow\(mix\(/);
  assert.ok(glsl.includes('max(L,vec3(0.))*exposure'));
  assert.ok(!glsl.includes('displayColor'));
});
