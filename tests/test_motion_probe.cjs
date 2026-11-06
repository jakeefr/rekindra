const test=require('node:test'),assert=require('node:assert/strict');
const {probeMotion}=require('../scripts/motion_probe.cjs');
function fixture(mode){
  let time=0;
  const runtime={scene:{duration:18,camera:[{eye:[0,0,5],target:[0,0,0],fov:45},{eye:[5,0,5],target:[0,0,0],fov:45}]},renderAt(t){time=t}};
  const canvas={width:1,height:1,getContext(){return {getImageData(){return {data:new Uint8ClampedArray([mode==='late'?Math.round(Math.max(0,time-3)*10):mode==='camera'?Math.round(time*(runtime.scene.camera[1].eye[0])):0,0,0,255])}}}}};
  return {runtime,canvas};
}
test('timeline probe accepts motion after opening hold',()=>{const f=fixture('late');assert.equal(probeMotion({...f,fixedCamera:true}).changed,true)});
test('timeline probe rejects frozen and camera-only worlds and restores camera',()=>{
  assert.equal(probeMotion(fixture('frozen')).changed,false);
  const f=fixture('camera'),saved=f.runtime.scene.camera;
  assert.equal(probeMotion(f).changed,true);
  assert.equal(probeMotion({...f,fixedCamera:true}).changed,false);
  assert.equal(f.runtime.scene.camera,saved);
});
test('timeline probe restores camera on capture failure',()=>{
  const f=fixture('late'),saved=f.runtime.scene.camera;f.canvas.getContext=()=>{throw Error('capture')};
  assert.throws(()=>probeMotion({...f,fixedCamera:true}),/capture/);assert.equal(f.runtime.scene.camera,saved);
});

