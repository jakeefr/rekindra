/* Original, bounded video-only VP8 WebM muxer. No external media engine. */
(function(root){
  'use strict';
  const join=parts=>{const out=new Uint8Array(parts.reduce((n,p)=>n+p.length,0));let i=0;for(const p of parts){out.set(p,i);i+=p.length}return out};
  function vint(n){
    if(!Number.isSafeInteger(n)||n<0)throw Error('Invalid EBML size');
    let width=1;while(n>=2**(7*width)-1&&width<8)width++;
    const out=new Uint8Array(width);let v=BigInt(n);for(let i=width-1;i>=0;i--){out[i]=Number(v&255n);v>>=8n}out[0]|=1<<(8-width);return out;
  }
  function uint(n,width){if(!Number.isSafeInteger(n)||n<0)throw Error('Invalid unsigned integer');width=width||Math.max(1,Math.ceil(Math.log2(n+1)/8));const b=new Uint8Array(width);let v=BigInt(n);for(let i=width-1;i>=0;i--){b[i]=Number(v&255n);v>>=8n}return b}
  const id=n=>uint(n),el=(n,body)=>join([id(n),vint(body.length),body]),u=(n,v,width)=>el(n,uint(v,width));
  const str=(n,s)=>el(n,new TextEncoder().encode(s));
  const float=n=>{const b=new Uint8Array(8);new DataView(b.buffer).setFloat64(0,n);return b};
  function muxWebM(chunks,width,height,durationMs){
    if(!Array.isArray(chunks)||!chunks.length||chunks.length>900||![width,height].every(n=>Number.isInteger(n)&&n>0&&n<=4096)||!Number.isFinite(durationMs)||durationMs<=0||durationMs>30000)throw Error('Invalid WebM bounds');
    let last=-1,total=0;
    for(const c of chunks){if(!Number.isSafeInteger(c.timestamp)||c.timestamp<=last||c.timestamp<0||c.timestamp>=durationMs*1000||!(c.data instanceof Uint8Array)||!['key','delta'].includes(c.type))throw Error('Invalid chunk sequence');last=c.timestamp;total+=c.data.length}
    if(chunks[0].type!=='key'||chunks[0].timestamp!==0||total>100_000_000)throw Error('Invalid keyframe or size budget');
    const header=el(0x1a45dfa3,join([u(0x4286,1),u(0x42f7,1),u(0x42f2,4),u(0x42f3,8),str(0x4282,'webm'),u(0x4287,4),u(0x4285,2)]));
    const info=el(0x1549a966,join([u(0x2ad7b1,1000000),str(0x4d80,'Rekindra'),str(0x5741,'Rekindra'),el(0x4489,float(durationMs))]));
    const tracks=el(0x1654ae6b,el(0xae,join([u(0xd7,1),u(0x73c5,1),u(0x83,1),str(0x86,'V_VP8'),el(0xe0,join([u(0xb0,width),u(0xba,height)]))])));
    const groups=[];let group;
    for(const c of chunks){const ms=Math.round(c.timestamp/1000);
      if(!group||(c.type==='key'&&ms-group.time>=1000)){group={time:ms,blocks:[]};groups.push(group)}
      const relative=ms-group.time;if(relative>32767)throw Error('Cluster timestamp overflow');
      const prefix=new Uint8Array([0x81,(relative>>8)&255,relative&255,c.type==='key'?0x80:0]);
      group.blocks.push(el(0xa3,join([prefix,c.data])));
    }
    const clusters=groups.map(g=>el(0x1f43b675,join([u(0xe7,g.time),...g.blocks])));
    const seek=pos=>el(0x114d9b74,el(0x4dbb,join([el(0x53ab,id(0x1c53bb6b)),u(0x53ac,pos,8)])));
    const headLength=seek(0).length;let position=headLength+info.length+tracks.length;
    const cues=[];
    groups.forEach((g,i)=>{cues.push(el(0xbb,join([u(0xb3,g.time),el(0xb7,join([u(0xf7,1),u(0xf1,position)]))])));position+=clusters[i].length});
    return join([header,el(0x18538067,join([seek(position),info,tracks,...clusters,el(0x1c53bb6b,join(cues))]))]);
  }
  const api={muxWebM,vint};if(typeof module!=='undefined')module.exports=api;else root.RekindraWebM=api;
})(globalThis);
