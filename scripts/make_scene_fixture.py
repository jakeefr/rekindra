"""Create rights-cleared procedural test material and a local authored scene."""
import json
import math
from pathlib import Path
import struct
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from rekindra_core.projects import ProjectStore
from rekindra_core.compositions import CompositionStore


def create(output: Path):
    source = output / 'inputs'; source.mkdir(parents=True, exist_ok=True)
    w,h=640,360
    pixels=bytearray()
    for y in range(h):
        for x in range(w):
            horizon=230+30*math.sin(x/95)+18*math.sin(x/37)
            glow=max(0,1-math.hypot((x-430)/260,(y-115)/180))
            r,g,b=12+int(35*glow),25+int(65*glow),30+int(30*glow)
            if (x-430)**2+(y-110)**2<34**2:r,g,b=210,226,165
            if y>horizon:r,g,b=12,25+int((h-y)/20),22
            for tree in (45,135,230,350,560):
                if abs(x-tree)<4 and y>80+tree%60:r,g,b=8,19,19
            pixels.extend((b,g,r))
    (source/'forgotten-garden.tga').write_bytes(struct.pack('<BBBHHBHHHHBB',0,0,2,0,0,0,0,0,w,h,24,32)+pixels)
    store=ProjectStore(output/'projects'); p=store.inspect(source);aid=p['assets'][0]['asset_id']
    scene={'schema_version':1,'title':'The garden after everyone left','mood':'dreamy / nocturnal / green',
           'reason':'An original interpretation of the recovered moonlit garden. </script><script>globalThis.injected=true</script>',
           'duration':4,'width':1280,'height':720,'background':'#0c2025','palette':['#c4d799','#e6ead8'],'seed':17,
           'layers':[{'id':'image','kind':'image','asset_id':aid,'start':0,'end':4,'x':.5,'y':.43,'width':.87,'height':.68,'motion':'drift'},
                     {'id':'fireflies','kind':'particles','start':0,'end':4,'x':.5,'y':.5,'width':1,'height':.8,'opacity':.7,'color':'#c4d799','count':70},
                     {'id':'title','kind':'text','start':0,'end':4,'x':.5,'y':.87,'width':.9,'height':.14,'text':'Something here still remembers.','font_size':43,'color':'#e6ead8','motion':'rise'}]}
    comps=CompositionStore(store);plan=comps.save_plan(p['project_id'],scene,[aid],{'provider':'local','model':'authored-test-fixture'})
    built=comps.build(p['project_id'],plan['plan_id'])
    result={'input_folder':str(source.resolve()),**built}
    (output/'result.json').write_text(json.dumps(result,indent=2),encoding='utf-8')
    return result


if __name__=='__main__':
    print(json.dumps(create(ROOT/'.local'/'scene-fixture'),indent=2))
