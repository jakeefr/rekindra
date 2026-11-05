const test=require('node:test');
const assert=require('node:assert/strict');
const {pose,trackAt,fragmentPose}=require('../runtime/scene.js');
const {muxWebM,vint}=require('../runtime/webm.js');

test('timeline evaluation is deterministic and bounded to its interval',()=>{
  const layer={start:1,end:5,x:.5,y:.5,opacity:1,rotation:0,motion:'drift'};
  assert.equal(pose(layer,0).active,false);
  assert.deepEqual(pose(layer,2),pose(layer,2));
  assert.notEqual(pose(layer,2).x,pose(layer,3).x);
  assert.equal(pose(layer,5).active,false);
});
test('authored tracks seek exactly and independently of playback history',()=>{
  const a={at:0,x:.2,y:.5,scale:1,rotation:0,opacity:1,spread:0,turn:0};
  const b={...a,at:4,x:.8,scale:2,spread:1,turn:90};
  assert.deepEqual(trackAt([a,b],0),a);
  assert.equal(trackAt([a,b],2).x,.5);
  const expected=trackAt([a,b],1.25);trackAt([a,b],3.7);
  assert.deepEqual(trackAt([a,b],1.25),expected);
  assert.equal(trackAt([a,b],10).x,.8);
  const origin=fragmentPose(0,0,4,2,0,0,0);
  assert.equal(origin.x,-.375);assert.equal(origin.y,-.25);
  const moved=fragmentPose(0,0,4,2,1,50,3);
  assert.notEqual(moved.x,origin.x);assert.ok(Number.isFinite(moved.z));
});
test('EBML sizes reserve the unknown-size sentinel',()=>{
  assert.deepEqual([...vint(0)],[128]);
  assert.deepEqual([...vint(126)],[254]);
  assert.deepEqual([...vint(127)],[64,127]);
  assert.throws(()=>vint(-1));
});
test('WebM rejects invalid dimensions, ordering and missing keyframe',()=>{
  const key={timestamp:0,type:'key',data:new Uint8Array([1,2])};
  for(const args of [[[],640,360,1000],[[key],0,360,1000],
    [[{...key,type:'delta'}],640,360,1000],[[key,key],640,360,1000]]){
      assert.throws(()=>muxWebM(...args));
  }
  const bytes=muxWebM([key],640,360,1000);
  assert.deepEqual([...bytes.slice(0,4)],[0x1a,0x45,0xdf,0xa3]);
  assert.ok(new TextDecoder().decode(bytes).includes('V_VP8'));
});
