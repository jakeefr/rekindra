const test=require('node:test'),assert=require('node:assert/strict');
const {cameraAt,basis,projectPoint}=require('../runtime/world.js');
test('camera interpolation and perspective are deterministic',()=>{
  const keys=[{at:0,eye:[0,2,8],target:[0,0,0],fov:50},{at:10,eye:[4,3,6],target:[0,0,0],fov:60}];
  const mid=cameraAt(keys,5);assert.deepEqual(mid.eye,[2,2.5,7]);assert.equal(mid.fov,55);
  assert.deepEqual(cameraAt(keys,5),mid);
  const b=basis(keys[0]);const center=projectPoint([0,0,0],keys[0],1280,720);
  assert.ok(Math.abs(center[0]-640)<1e-6);assert.ok(Math.abs(center[1]-360)<1e-6);
  assert.ok(Math.abs(b.right.reduce((s,x,i)=>s+x*b.forward[i],0))<1e-8);
  const vertical=basis({eye:[0,2,0],target:[0,0,0]});assert.ok(vertical.right.every(Number.isFinite));
});
