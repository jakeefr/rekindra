"""Original 24-program stress scene, not a generated artistic benchmark."""
import json
import sys
import time
from pathlib import Path
root=Path(__file__).resolve().parents[1];sys.path[:0]=[str(root),str(root/'tests'),str(root/'scripts')]
from test_worlds import world
from make_motion_study import source_image
from rekindra_core.projects import ProjectStore
from rekindra_core.compositions import CompositionStore
from rekindra_core.preview import preview_scene

out=root/'.local/construction-headroom';inputs=out/'inputs';inputs.mkdir(parents=True,exist_ok=True)
(inputs/'stress-source.png').write_bytes(source_image())
store=ProjectStore(out/'projects');project=store.inspect(inputs);pid=project['project_id'];aid=project['assets'][0]['asset_id']
s=world(aid);s['title']='Distinct-program capacity stress';s['duration']=6
s['camera']=[dict(at=t,eye=[0,10,20],target=[0,0,0],fov=48) for t in [0,6]]
s['environment'].update(fog_density=0,occlusion_strength=.4,occlusion_radius=.5,
    environment_panels=[dict(direction=d,color='#FFFFFF',intensity=2,size=[.15,.5],rotation=.2)
                        for d in [[-2,3,2],[2,3,-2],[0,1,0],[1,0,1]]])
s['objects']=[]
for i in range(24):
    x=(i%6-2.5)*2.2;z=(i//6-1.5)*2.6
    s['objects'].append(dict(id=f'part_{i}',bindings=[dict(name='r',expression=f'.55+.09*sin(t*2+{i})+.08*cos(v*6*pi)')],
        position=dict(x=f'{x}+r*cos(u*2*pi)',y=f'(v-.5)*2+.1*sin(t+{i})',z=f'{z}+r*sin(u*2*pi)'),
        segments=[32,40],caps=['v0','v1'],color='#245F78',color_high='#C4944D',color_mix=str(i/23),
        roughness=.15+(i%4)*.18,metalness=(i%3)*.4,emission=0))
comps=CompositionStore(store);plan=comps.save_plan(pid,s,[aid],dict(provider='local',model='24-program-stress-control'))
artifact=comps.build(pid,plan['plan_id']);start=time.monotonic();preview=preview_scene(store,pid,plan['plan_id'])
elapsed=time.monotonic()-start
result=dict(artifact=artifact,preview=preview,elapsed_seconds=elapsed,definitions=24,cells=31488)
(out/'result.json').write_text(json.dumps(result,indent=2));print(json.dumps(dict(elapsed_seconds=elapsed,html=artifact['path'],preview=preview.get('path'))))
assert elapsed<45,'Existing preview deadline must remain sufficient'
