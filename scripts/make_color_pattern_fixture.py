"""Controlled original material fixtures, independent of scene art direction."""
import copy
import json
import sys
from pathlib import Path

root = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(root), str(root/'tests')]
from test_worlds import world
from rekindra_core.worlds import compile_world, validate_world

s = world()
s['environment'].update(sky_top='#000000', sky_bottom='#000000', fog_density=0,
                        sun_strength=0, fill_strength=0, ambient_strength=0,
                        ground_strength=0, exposure=1)
s['camera'] = [{'at':t, 'eye':[0,0,8], 'target':[0,0,0], 'fov':50} for t in [0,12]]
s['objects'] = [dict(id='panel', position=dict(x='(u-.5)*8', y='(v-.5)*5', z='0'),
                    segments=[4,4], color='#000000', color_high='#FFFFFF',
                    color_mix='.5+.5*cos(u*8*pi)', roughness=1, metalness=0, emission=1)]
cases = {}
def save(name, scene):
    scene = validate_world(scene, {'a'*32})
    cases[name] = dict(scene=scene, programs=compile_world(scene))

save('legacy', s)
coarse = copy.deepcopy(s); coarse['objects'][0]['color_pattern'] = '.5+.5*cos(u*8*pi)'
save('coarse', coarse)
dense = copy.deepcopy(coarse); dense['objects'][0]['segments'] = [64,64]
save('dense', dense)
animated = copy.deepcopy(coarse); animated['objects'][0]['color_pattern'] = '.5+.5*cos(u*8*pi+t)'
save('animated', animated)
combined = copy.deepcopy(coarse)
combined['environment'].update(sun_strength=1,light_direction=[1,1,4])
combined['objects'][0].update(color_detail='.1*cos(v*8*pi)',bump_detail='.01*sin(u*8*pi)')
save('combined',combined)
for name, mix, pattern in [('constantLegacy','1',None),('constantPattern','1','1'),
                           ('clampLow','0','-10'),('clampHigh','1','10'),('black','0',None)]:
    c=copy.deepcopy(s);c['objects'][0]['color_mix']=mix
    if pattern is not None:c['objects'][0]['color_pattern']=pattern
    save(name,c)
cap = copy.deepcopy(s)
cap['camera'] = [{'at':t,'eye':[4,5,6],'target':[0,1,0],'fov':50} for t in [0,12]]
cap['objects'][0].update(position=dict(x='2*cos(u*2*pi)',y='v*2',z='2*sin(u*2*pi)'),
                         segments=[16,8], caps=['v0','v1'], color_mix='0')
save('capLegacy',cap)
cap['objects'][0]['color_pattern']='1'
save('capPattern',cap)
cap['objects'][0].update(color_detail='.1*cos(v*8*pi)',bump_detail='.01*sin(u*8*pi)')
save('capCombined',cap)
out=root/'.local/color-pattern';out.mkdir(parents=True,exist_ok=True)
(out/'fixtures.json').write_text(json.dumps(cases))
