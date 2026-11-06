// Self-contained so Playwright can serialize this function without eval/imports.
function probeMotion(options={}) {
  const runtime=options.runtime||globalThis.rekindra;
  const canvas=options.canvas||document.querySelector('#stage');
  const duration=runtime.scene.duration;
  if(!Number.isFinite(duration)||duration<=0)throw Error('Invalid motion duration');
  const saved=runtime.scene.camera;
  const times=Array.from({length:24},(_,i)=>duration*(i+.5)/24);
  let first,changed=false;
  try{
    if(options.fixedCamera)runtime.scene.camera=saved.map(k=>({...k,eye:saved[0].eye,target:saved[0].target,fov:saved[0].fov}));
    const ctx=canvas.getContext('2d');
    for(const time of times){
      runtime.renderAt(time);
      const pixels=ctx.getImageData(0,0,canvas.width,canvas.height).data;
      if(!first)first=new Uint8ClampedArray(pixels);
      else if(pixels.some((value,i)=>value!==first[i]))changed=true;
    }
    return {changed,times};
  }finally{runtime.scene.camera=saved;}
}
module.exports={probeMotion};
