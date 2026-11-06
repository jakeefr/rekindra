const {test}=require('node:test'),assert=require('node:assert/strict');
const world=require('../runtime/world.js');
test('cap fans share rim coordinates and remain within index bounds',()=>{
 const plain=world.surfaceMesh([8,4],[]),closed=world.surfaceMesh([8,4],['v0','v1']);
 assert.equal(plain.vertices.length/3,45);assert.equal(plain.indices.length,8*4*6);
 assert.equal(closed.vertices.length/3,65);assert.equal(closed.indices.length,8*4*6+8*3*2);
 assert.ok(closed.indices.every(i=>i>=0&&i<65));
 for(const start of [45,55]){
  const v=closed.vertices[start*3+1];assert.ok(v===0||v===1);
  assert.deepEqual(closed.vertices.slice(start*3,start*3+3),[0,v,1]);
  assert.deepEqual(closed.vertices.slice((start+1)*3,(start+1)*3+3),[0,v,2]);
  assert.deepEqual(closed.vertices.slice((start+9)*3,(start+9)*3+3),[1,v,2]);
 }
});
