"""Original synthetic source + authored motion study. No claim of model authorship."""
import json
import math
from pathlib import Path
import sys

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from rekindra_core.png import encode_png
from rekindra_core.tga import Raster
from rekindra_core.projects import ProjectStore
from rekindra_core.compositions import CompositionStore
from rekindra_core.scenes import enforce_text_preference


def source_image():
    w,h=960,540;pixels=bytearray()
    for y in range(h):
        v=y/h
        for x in range(w):
            u=x/w
            glow=math.exp(-((u-.62)**2*15+(v-.39)**2*13))
            sky=(9+int(95*glow),24+int(67*glow),42+int(42*glow))
            color=sky
            radius=math.hypot((u-.62)*w/h,v-.34)
            if radius<.115:
                color=(255,round(205-90*(v-.225)/.23),round(126-65*(v-.225)/.23))
            if v>.50:
                wave=math.sin(v*240+math.sin(u*14)*2)+.5*math.sin(v*470+u*27)
                reflection=math.exp(-((u-.62)/(.035+(v-.5)*.43))**2)*max(0,wave)*.7
                color=(12+int(reflection*180),39+int(reflection*100),51+int(reflection*48))
            for index in range(5):
                edge=.66+index*.075+.075*math.sin(u*5+index*.67)+.02*math.sin(u*13-index)
                if v>edge:
                    rim=math.exp(-(v-edge)*110)
                    color=(int(12+index*2+rim*30),int(64-index*8+rim*91),int(69-index*8+rim*78))
            vignette=max(.55,1-.35*((u-.5)**2+(v-.5)**2)*2)
            pixels.extend((*[max(0,min(255,round(c*vignette))) for c in color],255))
    return encode_png(Raster(w,h,bytes(pixels)))


def key(at,spread=0,turn=0,scale=1,x=.5,y=.5,rotation=0):
    return dict(at=at,spread=spread,turn=turn,scale=scale,x=x,y=y,rotation=rotation,opacity=1)


def main():
    out=ROOT/'.local/motion-study';inputs=out/'inputs';inputs.mkdir(parents=True,exist_ok=True)
    (inputs/'copper-tide.png').write_bytes(source_image())
    store=ProjectStore(out/'projects');p=store.inspect(inputs);aid=p['assets'][0]['asset_id']
    scene={'schema_version':1,'title':'Copper tide — motion study','mood':'warm light / cold water / suspended fragments',
           'reason':'Original synthetic artwork transformed into moving image fragments. A renderer study, not a recovered 3D scene or final product demo.',
           'duration':12,'width':1280,'height':720,'background':'#050c16','palette':['#f5c491','#68c3b7','#102c40'],'seed':37,
           'layers':[{'id':'tide','kind':'fragments','asset_id':aid,'start':0,'end':12,'x':.5,'y':.5,
                      'width':.88,'height':.88,'columns':24,'rows':14,
                      'track':[key(0,scale=1.12),key(1.4,scale=1.12),key(3.5,.8,-32,.82),
                               key(5.5,1,38,.92),key(7.5,.9,-48,.85),key(10.5,0,0,1.12),key(12,scale=1.12)]}]}
    enforce_text_preference(scene)
    comps=CompositionStore(store);plan=comps.save_plan(p['project_id'],scene,[aid],{'provider':'local','model':'authored-motion-study'})
    artifact=comps.build(p['project_id'],plan['plan_id'])
    (out/'result.json').write_text(json.dumps(artifact,indent=2),encoding='utf-8')
    print(json.dumps(artifact,indent=2))


if __name__=='__main__':main()
