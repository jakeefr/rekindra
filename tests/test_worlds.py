import copy
import unittest
import json
from pathlib import Path
import test_projects
from test_tga import fixture
from rekindra_core.expressions import compile_expression
from rekindra_core.worlds import validate_world
from rekindra_core.scenes import SceneError


def world(aid='a'*32):
    return {'schema_version':2,'title':'Copper water','mood':'warm horizon, cold waves','reason':'Generated moving geometry inspired by source colors.',
            'duration':12,'width':1280,'height':720,'seed':23,
            'references':[{'asset_id':aid,'observed':'An orange sun above teal curved bands.','created':'Animated water and warm horizon lighting.'}],
            'environment':{'sky_top':'#101c38','sky_bottom':'#dca07d','fog_color':'#778c9b','fog_density':.025,
                           'light_color':'#ffd4a0','light_direction':[.3,.2,-1],'sun_size':.025,'sun_strength':1.5},
            'camera':[{'at':0,'eye':[4,2.6,8],'target':[0,0,-3],'fov':52},
                      {'at':12,'eye':[-3,2.1,6],'target':[0,0,-4],'fov':52}],
            'objects':[{'id':'sea','position':{'x':'(u-.5)*36','y':'.18*sin(u*44+t*1.4)+.09*cos(v*53-t)','z':'(v-.5)*36'},
                        'segments':[96,64],'color':'#164450','color_high':'#55a798','color_mix':'.5+.3*sin(u*30+t)',
                        'roughness':.17,'metalness':.55,'emission':0}]}


class WorldTests(unittest.TestCase):
    def test_expression_whitelist(self):
        result=compile_expression('.2*sin(u*12+t)+cos(v*pi)')
        self.assertIn('sin',result['glsl']);self.assertGreater(result['cost'],1)
        for expr in ('__import__("os")','u.x','u[0]','[u for u in x]','sin(u,v)','nan','1e999','2**999','u; discard;', 'True'):
            with self.subTest(expr=expr),self.assertRaises(SceneError):compile_expression(expr)
        with self.assertRaises(SceneError):compile_expression('sin('*30+'u'+')'*30)

    def test_generated_world_does_not_require_image_layers(self):
        s=world();result=validate_world(s,{'a'*32})
        self.assertEqual(result['schema_version'],2)
        self.assertNotIn('layers',result)
        self.assertEqual(result,s)

    def test_rejects_ungrounded_or_unbounded_worlds(self):
        for change in ('source','geometry','code','camera','camera_crossing','light'):
            s=world()
            if change=='source':s['references'][0]['asset_id']='b'*32
            if change=='geometry':s['objects'][0]['segments']=[10000,10000]
            if change=='code':s['objects'][0]['position']['x']='fetch("https://evil")'
            if change=='camera':s['camera'][0]['eye']=s['camera'][0]['target']
            if change=='camera_crossing':
                s['camera'][0].update(eye=[0,0,1],target=[0,0,0]);s['camera'][1].update(eye=[0,0,-1],target=[0,0,0])
            if change=='light':s['environment']['light_direction']=[0,0,0]
            with self.subTest(change=change),self.assertRaises(SceneError):validate_world(s,{'a'*32})


class WorldIntegrationTests(unittest.TestCase):
    setUp=test_projects.ProjectTests.setUp
    def test_tool_builds_source_grounded_geometry_without_image_layers(self):
        from test_plugin import plugin
        (self.source/'old.tga').write_bytes(fixture())
        p=self.store.inspect(self.source);aid=p['assets'][0]['asset_id']
        handlers=plugin.handlers.make_handlers(lambda:self.store)
        result=json.loads(handlers['rekindra_create_world']({'project_id':p['project_id'],'asset_ids':[aid],'scene':world(aid)}))
        self.assertTrue(result['ok'],result)
        document=Path(result['result']['path']).read_text(encoding='utf8')
        self.assertIn('RekindraWorld',document)
        self.assertIn('"programs"',document)
