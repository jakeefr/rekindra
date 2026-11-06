import json,sys
from pathlib import Path
root=Path(__file__).resolve().parents[1];sys.path.insert(0,str(root));sys.path.insert(0,str(root/'tests'))
from test_worlds import world
from rekindra_core.worlds import compile_world
s=world();s['environment'].update(sky_top='#FFFFFF',sky_bottom='#FFFFFF',fog_density=0,ambient_strength=1,fill_strength=0,sun_strength=0,exposure=1)
s['camera']=[{'at':t,'eye':[5,4,7],'target':[0,.5,0],'fov':50} for t in [0,12]]
def surface(id,pos):return dict(id=id,position=pos,segments=[4,4],color='#777777',color_high='#777777',color_mix='0',roughness=1,metalness=0,emission=0)
s['objects']=[surface('floor',dict(x='(u-.5)*14',y='0',z='(v-.5)*14')),surface('wall',dict(x='(u-.5)*8',y='v*3',z='0'))]
(root/'.local/contact-depth').mkdir(exist_ok=True)
(root/'.local/contact-depth/fixture.json').write_text(json.dumps({'scene':s,'programs':compile_world(s)}))

