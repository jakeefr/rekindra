"""Isolated mirror controls using Rekindra's own scene representation."""
import copy,json,sys
from pathlib import Path
root=Path(__file__).resolve().parents[1];sys.path[:0]=[str(root),str(root/'tests')]
from test_worlds import world
from rekindra_core.worlds import validate_world,compile_world
s=world();s['environment'].update(sky_top='#000000',sky_bottom='#000000',fog_density=0,
    sun_strength=0,fill_strength=0,ambient_strength=0)
s['camera']=[dict(at=t,eye=[0,4,8],target=[0,.5,0],fov=50) for t in [0,12]]
floor=dict(id='floor',position=dict(x='(u-.5)*32',y='0',z='(v-.5)*32'),segments=[4,4],
    color='#000000',color_high='#000000',color_mix='0',roughness=.1,metalness=0,emission=0)
red=dict(id='red',position=dict(x='-1.2+.6*sin(t)+.55*cos(u*2*pi)*sin(v*pi)',y='1.5+.55*cos(v*pi)',z='.55*sin(u*2*pi)*sin(v*pi)'),
    segments=[48,32],color='#FF0000',color_high='#FF0000',color_mix='0',roughness=.4,metalness=0,emission=1)
blue=copy.deepcopy(red);blue.update(id='blue',color='#0000FF',color_high='#0000FF');blue['position']['x']='1.2+.4*cos(u*2*pi)*sin(v*pi)'
blue['position']['y']='1.8+.4*cos(v*pi)'
s['objects']=[floor,red,blue];cases={}
def save(name,c):
    c=validate_world(c,{'a'*32});cases[name]=dict(scene=c,programs=compile_world(c))
save('legacy',copy.deepcopy(s));s['objects'][0]['reflection']=dict(strength=0,blur=0);save('off',copy.deepcopy(s))
s['objects'][0]['reflection']['strength']=1;save('sharp',copy.deepcopy(s))
c=copy.deepcopy(s);c['objects'][0]['reflection']['blur']=6;save('blurred',c)
c=copy.deepcopy(s);hidden=copy.deepcopy(red);hidden.update(id='below',color='#00FF00',color_high='#00FF00');hidden['position']['y']='-1.5+.55*cos(v*pi)';c['objects'].append(hidden);save('clipped',c)
c=copy.deepcopy(s);c['objects'][0]['position']['y']='1';c['objects'][1]['position']['y']='2.5+.55*cos(v*pi)';c['objects'][2]['position']['y']='2.8+.4*cos(v*pi)';save('raised',c)
c=copy.deepcopy(s);c['camera'][1]['eye']=[2,5,9];save('cameraMotion',c)
c=copy.deepcopy(s);c['environment'].update(occlusion_strength=.4,occlusion_radius=.5,
    environment_panels=[dict(direction=[-1,2,3],color='#FFFFFF',intensity=1,size=[.2,.5],rotation=.2)])
save('combined',c)
plain=copy.deepcopy(c);del plain['objects'][0]['reflection'];save('legacyAO',plain)
plain['objects'][0]['reflection']=dict(strength=0,blur=0);save('offAO',plain)
c['objects'][1].update(position=dict(x='-1.2+.6*sin(t)+.55*cos(u*2*pi)',y='1.5+(v-.5)',z='.55*sin(u*2*pi)'),caps=['v0','v1'])
save('combinedCaps',c)
c=copy.deepcopy(s);c['camera']=[dict(at=t,eye=[0,-4,8],target=[0,-.5,0],fov=50) for t in [0,12]];save('under',copy.deepcopy(c));del c['objects'][0]['reflection'];save('underOff',c)
out=root/'.local/planar-reflection';out.mkdir(parents=True,exist_ok=True);(out/'fixtures.json').write_text(json.dumps(cases))
