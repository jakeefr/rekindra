"""Private original geometry control for shot timing; not an artistic submission."""
import json,sys
from pathlib import Path
root=Path(__file__).resolve().parents[1];sys.path[:0]=[str(root),str(root/'scripts')]
from rekindra_core.projects import ProjectStore
from rekindra_core.compositions import CompositionStore
from rekindra_core.worlds import validate_world,compile_world
from make_motion_study import source_image

out=root/'.local/camera-cuts';inputs=out/'inputs';inputs.mkdir(parents=True,exist_ok=True)
(inputs/'source.png').write_bytes(source_image());store=ProjectStore(out/'projects');p=store.inspect(inputs);aid=p['assets'][0]['asset_id']
material=dict(color='#CB3827',color_high='#F19A4C',color_mix='.4',roughness=.3,metalness=.12,emission=0)
sphere=dict(id='moving',position=dict(x='1.4*sin(t*1.7)+cos(u*2*pi)*sin(v*pi)*.8',y='1.4+cos(v*pi)*.8',z='sin(u*2*pi)*sin(v*pi)*.8'),segments=[48,24],**material)
floor=dict(id='floor',position=dict(x='(u-.5)*24',y='0',z='(v-.5)*24'),segments=[4,4],**{**material,'color':'#17383E','color_high':'#244F56','roughness':.25,'metalness':0},reflection=dict(strength=.5,blur=.4))
scene=dict(schema_version=2,title='Camera cut control',mood='Technical red sphere on teal reflector',reason='Original technical control for camera cuts and continuous global object time.',duration=6,width=1280,height=720,seed=1,references=[dict(asset_id=aid,observed='Constructed color fixture.',created='Original animated sphere and reflector for camera regression.')],environment=dict(sky_top='#182B42',sky_bottom='#7D9FAD',fog_color='#182B42',fog_density=0,light_color='#FFF1D4',light_direction=[-3,5,6],sun_size=.08,sun_strength=1.4,fill_strength=.2),camera=[dict(at=0,eye=[0,3,8],target=[0,1,0],fov=40),dict(at=2.013,eye=[5,2,5],target=[0,1,0],fov=35,cut=True),dict(at=4,eye=[-5,4,5],target=[0,1,0],fov=45,cut=True),dict(at=6,eye=[-5,4,5],target=[0,1,0],fov=45)],objects=[sphere,floor])
scene=validate_world(scene,{aid});(out/'fixture.json').write_text(json.dumps(dict(scene=scene,programs=compile_world(scene)),indent=2))
comps=CompositionStore(store);plan=comps.save_plan(p['project_id'],scene,[aid],dict(provider='local',model='camera-cut-control'));artifact=comps.build(p['project_id'],plan['plan_id'])
(out/'artifact.json').write_text(json.dumps(artifact,indent=2));print(artifact['path'])
