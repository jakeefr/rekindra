"""Isolated original lighting controls; not an artistic acceptance test."""
import copy
import json
import sys
from pathlib import Path
root=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(root),str(root/'tests')]
from test_worlds import world
from rekindra_core.worlds import compile_world, validate_world

s=world()
s['environment'].update(sky_top='#000000',sky_bottom='#000000',fog_density=0,
    sun_strength=0,fill_strength=0,ambient_strength=0,exposure=1)
s['camera']=[dict(at=t,eye=[0,0,8],target=[0,0,0],fov=50) for t in [0,12]]
s['objects']=[dict(id='receiver',position=dict(x='(u-.5)*12',y='(v-.5)*8',z='0'),
    segments=[4,4],color='#AAAAAA',color_high='#AAAAAA',color_mix='0',
    roughness=.08,metalness=1,emission=0)]
p=dict(direction=[0,0,1],color='#FFFFFF',intensity=4,size=[.08,.5],rotation=0)
cases={}
def save(name,scene):
    scene=validate_world(scene,{'a'*32})
    cases[name]=dict(scene=scene,programs=compile_world(scene))
save('legacy',copy.deepcopy(s))
c=copy.deepcopy(s);c['environment'].update(sky_top='#3C6A91',sky_bottom='#B89B72',
    sun_strength=1.5,fill_strength=.2,ambient_strength=.6)
save('litLegacy',copy.deepcopy(c))
c['environment']['environment_panels']=[];save('litEmpty',copy.deepcopy(c))
c['environment']['environment_panels']=[dict(p,intensity=0)];save('litOff',copy.deepcopy(c))
s['environment']['environment_panels']=[];save('empty',copy.deepcopy(s))
s['environment']['environment_panels']=[dict(p,intensity=0)];save('off',copy.deepcopy(s))
s['environment']['environment_panels']=[p];save('gloss',copy.deepcopy(s))
c=copy.deepcopy(s);c['objects'][0]['roughness']=.65;save('rough',c)
c=copy.deepcopy(s);c['environment']['environment_panels'][0]['rotation']=1.5707963267948966;save('rotated',c)
c=copy.deepcopy(s);c['objects'][0].update(metalness=0,roughness=1);save('diffuse',c)
c=copy.deepcopy(s);c['environment']['environment_panels'][0]['direction']=[0,0,-1];save('behind',c)
c=copy.deepcopy(s);c['camera'][1]['eye']=[2,0,8];save('moving',c)
c=copy.deepcopy(s);c['environment']['environment_panels']=[dict(p,direction=d,rotation=.3) for d in [[0,1,0],[0,-1,0],[1,0,1],[-1,0,1]]]
c['environment'].update(occlusion_strength=.5,occlusion_radius=.4)
c['objects'][0].update(position=dict(x='cos(u*2*pi)',y='(v-.5)*3',z='sin(u*2*pi)'),
    segments=[48,16],caps=['v0','v1'],bump_detail='.002*sin(u*40)',color_pattern='.5+.2*cos(v*8)')
c['camera']=[dict(at=t,eye=[4,3,6],target=[0,0,0],fov=50) for t in [0,12]]
save('combined',c)
out=root/'.local/environment-panels';out.mkdir(parents=True,exist_ok=True)
(out/'fixtures.json').write_text(json.dumps(cases))
