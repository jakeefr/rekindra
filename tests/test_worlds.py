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
    def test_surface_id_limit_is_advertised_and_actionable(self):
        from rekindra_core.worlds import WORLD_SCHEMA
        field=WORLD_SCHEMA['properties']['objects']['items']['properties']['id']
        self.assertEqual(field['maxLength'],40)
        s=world();s['objects'][0]['id']='x'*41
        with self.assertRaisesRegex(SceneError,'40'):validate_world(s, {'a'*32})

    def test_instances_validate_and_charge_repeated_geometry(self):
        s=world();o=s['objects'][0]
        o['instances']=[{'offset':[1,2,3],'scale':[1,.5,2]}]
        self.assertEqual(validate_world(s, {'a'*32})['objects'][0]['instances'],o['instances'])
        for invalid in ([],[{'offset':[0,0,0],'scale':[1,0,1]}],[{'offset':[0,0,0],'scale':[1,1,1],'extra':1}]):
            o['instances']=invalid
            with self.assertRaises(SceneError):validate_world(s, {'a'*32})
        o['instances']=[{'offset':[0,0,0],'scale':[1,1,1]}]*6
        with self.assertRaisesRegex(SceneError,'budget'):validate_world(s, {'a'*32})
        o['segments']=[4,4];o['instances']=o['instances']*2
        s['objects']=[dict(o,id=f'p{i}') for i in range(6)]
        with self.assertRaisesRegex(SceneError,'64'):validate_world(s, {'a'*32})
        s['objects']=[o];o['color_detail']='.2*sin(u*80)*sin(v*80)'
        with self.assertRaisesRegex(SceneError,'detail'):validate_world(s, {'a'*32})

    def test_caps_are_optional_unique_and_budgeted(self):
        s=world();s['objects'][0]['caps']=['v0','v1']
        self.assertEqual(validate_world(s, {'a'*32})['objects'][0]['caps'],['v0','v1'])
        for invalid in (['u0'],['v0','v0'],'v0',[False],['v1',{}]):
            s['objects'][0]['caps']=invalid
            with self.assertRaises(SceneError):validate_world(s, {'a'*32})
        s=world();o=s['objects'][0];o['segments']=[100,80]
        s['objects']=[dict(o,id=f'p{i}') for i in range(4)]
        validate_world(s, {'a'*32})
        s['objects'][0]['caps']=['v0','v1']
        with self.assertRaisesRegex(SceneError,'budget'):validate_world(s, {'a'*32})

    def test_bump_detail_is_bounded_and_shares_fragment_budget(self):
        from rekindra_core.worlds import compile_world
        s=world();s['objects'][0]['bump_detail']='.02*sin(u*80+t)*sin(v*80)'
        self.assertIn('sin',compile_world(validate_world(s, {'a'*32}))[0]['bump_detail'])
        for invalid in ('shape','__import__("os")','+'.join(['u']*20)):
            s['objects'][0]['bump_detail']=invalid
            with self.assertRaises(SceneError):validate_world(s, {'a'*32})
        s=world();o=s['objects'][0];o['segments']=[4,4]
        o['bump_detail']=o['color_detail']='+'.join(['u']*15)
        s['objects']=[dict(o,id=f's{i}') for i in range(3)]
        with self.assertRaisesRegex(SceneError,'detail'):validate_world(s, {'a'*32})

    def test_fragment_detail_compiles_without_geometry_bindings(self):
        from rekindra_core.worlds import compile_world
        s=world();s['objects'][0]['color_detail']='.2*sin(u*80)*sin(v*80)'
        valid=validate_world(s, {'a'*32})
        self.assertIn('sin',compile_world(valid)[0]['color_detail'])
        self.assertNotIn('color_detail',compile_world(world())[0])
        s['objects'][0]['bindings']=[{'name':'shape','expression':'u*2'}]
        s['objects'][0]['color_detail']='shape'
        with self.assertRaises(SceneError):validate_world(s, {'a'*32})

    def test_fragment_detail_has_separate_per_pixel_work_bounds(self):
        s=world();s['objects'][0]['color_detail']='+'.join(['u']*20)
        with self.assertRaisesRegex(SceneError,'detail'):validate_world(s, {'a'*32})
        s=world();s['objects'][0]['segments']=[4,4]
        s['objects'][0]['color_detail']='+'.join(['u']*15)
        s['objects']=[dict(s['objects'][0],id=f's{i}') for i in range(5)]
        with self.assertRaisesRegex(SceneError,'detail'):validate_world(s, {'a'*32})
        s=world();s['objects'][0]['color_detail']='__import__("os")'
        with self.assertRaises(SceneError):validate_world(s, {'a'*32})

    def test_model_schema_advertises_metadata_limits_enforced_at_runtime(self):
        # Live Hermes generated an overlong mood because its tool schema omitted
        # the runtime limit. Compare the advertised contract at each boundary.
        from rekindra_core.worlds import WORLD_SCHEMA
        props = WORLD_SCHEMA['properties']
        for name, limit in [('title', 100), ('mood', 100), ('reason', 600),
                            ('observed', 500), ('created', 500)]:
            with self.subTest(name=name):
                field = props[name] if name in props else props['references']['items']['properties'][name]
                self.assertEqual(field.get('maxLength'), limit)
                s = world()
                target = s if name in props else s['references'][0]
                target[name] = 'x' * limit
                validate_world(s, {'a'*32})
                target[name] += 'x'
                with self.assertRaises(SceneError):
                    validate_world(s, {'a'*32})

    def test_expression_whitelist(self):
        result=compile_expression('.2*sin(u*12+t)+cos(v*pi)')
        self.assertIn('sin',result['glsl']);self.assertGreater(result['cost'],1)
        for expr in ('__import__("os")','u.x','u[0]','[u for u in x]','sin(u,v)','nan','1e999','2**999','u; discard;', 'True'):
            with self.subTest(expr=expr),self.assertRaises(SceneError):compile_expression(expr)
        with self.assertRaises(SceneError):compile_expression('sin('*30+'u'+')'*30)
        with self.assertRaises(SceneError):compile_expression('9'*400)

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
        scene=world(aid);scene['objects'][0]['color_detail']='.1*sin(u*90)'
        result=json.loads(handlers['rekindra_create_world']({'project_id':p['project_id'],'asset_ids':[aid],'scene':scene}))
        self.assertTrue(result['ok'],result)
        document=Path(result['result']['path']).read_text(encoding='utf8')
        self.assertIn('RekindraWorld',document)
        self.assertIn('"programs"',document)
        self.assertIn('"color_detail"',document)
