"""Authored development benchmark for generated geometry; never labelled model output."""
import json
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from make_motion_study import source_image
from rekindra_core.projects import ProjectStore
from rekindra_core.compositions import CompositionStore


def surface(name,x,y,z,color,high,rough=.2,metal=.5,emission=0,segments=None,mix='.5'):
    return dict(id=name,position=dict(x=x,y=y,z=z),segments=segments or [96,48],color=color,color_high=high,
                color_mix=mix,roughness=rough,metalness=metal,emission=emission)


def main():
    out=ROOT/'.local/world-fixture';inputs=out/'inputs';inputs.mkdir(parents=True,exist_ok=True)
    (inputs/'copper-tide.png').write_bytes(source_image())
    store=ProjectStore(out/'projects');p=store.inspect(inputs);aid=p['assets'][0]['asset_id']
    world={'schema_version':2,'title':'After the tide','mood':'copper light / living water / impossible architecture',
           'reason':'Generated water, a breathing copper ring and an orbiting light interpret the source palette and curves. The source image itself is not drawn.',
           'duration':12,'width':1280,'height':720,'seed':41,
           'references':[{'asset_id':aid,'observed':'Orange circular sun, teal curved bands and a warm reflection.','created':'Moving water geometry, a copper ring and suspended light; these structures are invented.'}],
           'environment':{'sky_top':'#121c35','sky_bottom':'#e9a076','fog_color':'#748d91','fog_density':.025,
                          'light_color':'#ffd6a3','light_direction':[-.25,.21,-1],'sun_size':.033,'sun_strength':2.1},
           'camera':[{'at':0,'eye':[5,2.6,9],'target':[0,1,-5],'fov':52},
                     {'at':6,'eye':[0,1.7,6],'target':[0,1.4,-5],'fov':52},
                     {'at':12,'eye':[-4,2.9,8],'target':[0,1.2,-5],'fov':52}],
           'objects':[
               surface('water','(u-.5)*44','.16*sin(u*70+t*1.5)+.09*sin(v*92+t*.9)+.06*sin((u+v)*130-t*1.9)','(v-.5)*44',
                       '#07353e','#2c8279',.13,.65,segments=[128,96],mix='.5+.2*sin(u*43+v*31+t)'),
               surface('copper-ring','cos(u*2*pi)*(2.3+.19*cos(v*2*pi))','2.8+sin(u*2*pi)*(2.3+.19*cos(v*2*pi))',
                       '-5+.19*sin(v*2*pi)+.18*sin(t*.6+u*2*pi)','#925235','#e7af73',.22,.75,.12,mix='.5+.4*sin(u*2*pi+t*.3)'),
               surface('orbiting-light','2.9*cos(t*.45)+.22*cos(u*2*pi)*sin(v*pi)',
                       '1.5+.3*sin(t*.8)+.22*cos(v*pi)','-4+1.1*sin(t*.45)+.22*sin(u*2*pi)*sin(v*pi)',
                       '#ff864b','#ffe7b8',.2,.1,2.5,[48,24],'.6')
           ]}
    comps=CompositionStore(store);plan=comps.save_plan(p['project_id'],world,[aid],{'provider':'local','model':'authored-geometry-benchmark'})
    result=comps.build(p['project_id'],plan['plan_id']);(out/'result.json').write_text(json.dumps(result,indent=2),encoding='utf8');print(json.dumps(result,indent=2))


if __name__=='__main__':main()
