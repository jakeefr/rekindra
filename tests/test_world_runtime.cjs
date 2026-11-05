const test=require('node:test'),assert=require('node:assert/strict');
const {cameraAt,basis,projectPoint,cameraFrame,DEPTH_A,DEPTH_B}=require('../runtime/world.js');
test('camera orientation stays continuous near a vertical direction',()=>{
  const target=y=>[Math.sqrt(1-y*y),y,0];
  const keys=[{at:0,eye:[0,0,0],target:target(.98999),fov:50},{at:10,eye:[0,0,0],target:target(.99001),fov:50}];
  const a=cameraFrame(keys,4.9).basis.right,b=cameraFrame(keys,5.1).basis.right;
  assert.ok(a.reduce((s,x,i)=>s+x*b[i],0)>.9999);
  assert.deepEqual(cameraFrame(keys,4.9).basis.right,a);
  assert.ok(DEPTH_A*160-DEPTH_B<160,'Valid distant plane clipped by far limit');
});
test('camera interpolation and perspective are deterministic',()=>{
  const keys=[{at:0,eye:[0,2,8],target:[0,0,0],fov:50},{at:10,eye:[4,3,6],target:[0,0,0],fov:60}];
  const mid=cameraAt(keys,5);assert.deepEqual(mid.eye,[2,2.5,7]);assert.equal(mid.fov,55);
  assert.deepEqual(cameraAt(keys,5),mid);
  const b=basis(keys[0]);const center=projectPoint([0,0,0],keys[0],1280,720);
  assert.ok(Math.abs(center[0]-640)<1e-6);assert.ok(Math.abs(center[1]-360)<1e-6);
  assert.ok(Math.abs(b.right.reduce((s,x,i)=>s+x*b.forward[i],0))<1e-8);
  const vertical=basis({eye:[0,2,0],target:[0,0,0]});assert.ok(vertical.right.every(Number.isFinite));
});
