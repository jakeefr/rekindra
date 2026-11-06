const test=require('node:test'),assert=require('node:assert/strict');
const {cameraAt,basis,projectPoint,cameraFrame,DEPTH_A,DEPTH_B}=require('../runtime/world.js');
test('cuts hold the old pose, jump exactly, then resume interpolation',()=>{
 const keys=[{at:0,eye:[0,0,4],target:[0,0,0],fov:50},{at:1.013,eye:[0,0,-4],target:[0,0,0],fov:30,cut:true},{at:3.013,eye:[4,0,-4],target:[0,0,0],fov:50}];
 assert.deepEqual(cameraAt(keys,1.0129).eye,[0,0,4]);
 assert.deepEqual(cameraAt(keys,1.013).eye,[0,0,-4]);
 assert.deepEqual(cameraAt(keys,2.013).eye,[2,0,-4]);
 assert.equal(cameraAt(keys,2.013).fov,40);
 assert.deepEqual(cameraAt(keys,3.013).eye,[4,0,-4]);
});
test('nongrid closely spaced cuts reset orientation and remain seek independent',()=>{
 const keys=[{at:0,eye:[0,0,4],target:[0,0,0],fov:50},{at:1.011,eye:[0,4,0],target:[0,0,0],fov:40,cut:true},{at:1.019,eye:[4,0,0],target:[0,0,0],fov:30,cut:true},{at:2,eye:[4,0,0],target:[0,0,0],fov:30}];
 for(const index of [1,2])assert.deepEqual(cameraFrame(keys,keys[index].at).basis,basis(keys[index]));
 const before=cameraFrame(keys,1.0109),after=cameraFrame(keys,1.02);
 assert.deepEqual(before.basis,basis(keys[0]));assert.deepEqual(after.basis,basis(keys[2]));
 for(const t of [2,0,1.5,1.011,1.018,1.019])cameraFrame(keys,t);
 assert.deepEqual(cameraFrame(keys,1.0109),before);assert.deepEqual(cameraFrame(keys,1.02),after);
});
test('explicit false cuts preserve old camera samples exactly',()=>{
 const keys=[{at:0,eye:[4,2,8],target:[0,0,0],fov:50},{at:12,eye:[-3,3,6],target:[0,0,-1],fov:40}];
 const off=keys.map(k=>({...k,cut:false}));
 for(const t of [0,.01,1.019,5,11.99,12]){
  const a=cameraFrame(keys,t),b=cameraFrame(off,t);assert.deepEqual(a.basis,b.basis);
  for(const field of ['eye','target','fov'])assert.deepEqual(a.camera[field],b.camera[field]);
 }
});
test('a cut at final duration takes effect only at its exact endpoint',()=>{
 const keys=[{at:0,eye:[0,3,4],target:[0,0,0],fov:50},{at:6,eye:[0,-3,-4],target:[0,0,0],fov:30,cut:true}];
 // Orientation is numeric: cross/transport may canonicalize signed zero.
 for(const [t,k]of [[5.99999,keys[0]],[6,keys[1]]])for(const axis of ['forward','right','up'])
  cameraFrame(keys,t).basis[axis].forEach((v,i)=>assert.ok(Math.abs(v-basis(k)[axis][i])<1e-12));
 assert.deepEqual(cameraFrame(keys,6).camera.eye,keys[1].eye);
});
test('rounding a time just below a cut must not use its future orientation',()=>{
 const cut=23/30,before=0.7666666666666666;
 assert.ok(before<cut);assert.equal(Math.floor(before*30),23);
 const keys=[{at:0,eye:[0,3,4],target:[0,0,0],fov:50},{at:cut,eye:[3,4,0],target:[0,0,0],fov:30,cut:true},{at:6,eye:[3,4,0],target:[0,0,0],fov:30}];
 for(const [t,k]of [[before,keys[0]],[cut,keys[1]],[0.7666666666666668,keys[1]]])for(const axis of ['forward','right','up'])
  cameraFrame(keys,t).basis[axis].forEach((v,i)=>assert.ok(Math.abs(v-basis(k)[axis][i])<1e-12));
});
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
