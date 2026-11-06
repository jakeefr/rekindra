import copy
import unittest
from test_worlds import world
from rekindra_core.worlds import validate_world, WORLD_SCHEMA
from rekindra_core.scenes import SceneError

class LocalLightTests(unittest.TestCase):
    def test_valid_optional_bounded_lights(self):
        s=world();s['environment']['point_lights']=[{'position':[0,2,0],'color':'#FFA040','intensity':12,'range':8}]*4
        self.assertEqual(validate_world(s,{'a'*32}),s)
        self.assertEqual(WORLD_SCHEMA['properties']['environment']['properties']['point_lights']['maxItems'],4)
        s['environment']['point_lights']=[];validate_world(s,{'a'*32})
    def test_reject_invalid_lights(self):
        light={'position':[0,2,0],'color':'#FFA040','intensity':12,'range':8}
        invalid=[None,{},[light]*5]
        for key,value in [('position',[0,float('nan'),0]),('position',[81,0,0]),('position',[0,True,0]),('color','red'),('intensity',-1),('intensity',201),('intensity',float('inf')),('intensity',True),('range',0),('range',81),('extra',1)]:
            bad=copy.deepcopy(light);bad[key]=value;invalid.append([bad])
        for lights in invalid:
            s=world();s['environment']['point_lights']=lights
            with self.subTest(lights=lights),self.assertRaises(SceneError):validate_world(s,{'a'*32})
