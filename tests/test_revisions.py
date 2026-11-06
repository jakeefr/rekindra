import copy
import json
from pathlib import Path
import tempfile
import unittest

from test_worlds import world
from test_tga import fixture
from test_plugin import plugin
from rekindra_core.projects import ProjectStore
from rekindra_core.compositions import CompositionStore
from rekindra_core.revisions import revise_world
from rekindra_core.scenes import SceneError


class RevisionTests(unittest.TestCase):
    def test_public_contract_and_bounded_batch(self):
        schema=plugin.schemas.SCHEMAS['rekindra_revise_world']
        self.assertEqual(schema['parameters']['properties']['edits']['maxItems'],24)
        manifest=(Path(__file__).resolve().parents[1]/'plugin.yaml').read_text()
        self.assertIn('  - rekindra_revise_world\n',manifest)
        for edits in ([{'field':'title','value':'x'}]*25,
                      [{'field':'title','value':'x'},{'object_id':'sea','field':'segments','value':[128,96]},
                       {'object_id':'sea','field':'instances','value':[{'offset':[0,0,0],'scale':[1,1,1]}]*16}]):
            scene=world();before=copy.deepcopy(scene)
            with self.assertRaises(SceneError):revise_world(scene,edits,{'a'*32})
            self.assertEqual(scene,before)

    def test_targeted_change_preserves_other_fields_and_input(self):
        scene = world()
        scene['objects'].append(dict(scene['objects'][0], id='other', segments=[4,4]))
        before = copy.deepcopy(scene)
        result, changed = revise_world(scene, [{'object_id':'sea','field':'roughness','value':.8}], {'a'*32})
        self.assertEqual(scene, before)
        self.assertEqual(result['objects'][1], before['objects'][1])
        expected = copy.deepcopy(before); expected['objects'][0]['roughness'] = .8
        self.assertEqual(result, expected)
        self.assertEqual(changed, ['objects/sea/roughness'])

    def test_rejects_bad_targets_duplicates_noops_and_invalid_final_world(self):
        for edits in ([], [{'field':'references','value':[]}],
                      [{'object_id':'absent','field':'roughness','value':.5}],
                      [{'object_id':'sea','field':'id','value':'new'}],
                      [{'object_id':'sea','field':'roughness','value':.17}],
                      [{'object_id':'sea','field':'roughness','value':8}],
                      [{'object_id':'sea','field':'roughness','value':None}],
                      [{'field':'title','value':'x','extra':1}],
                      [{'field':'title','value':'x'}]*2,
                      [{'object_id':None,'field':'title','value':'x'}]):
            with self.subTest(edits=edits), self.assertRaises(SceneError):
                revise_world(world(), edits, {'a'*32})

    def test_optional_removal_and_camera_replacement(self):
        scene=world(); scene['objects'][0]['bump_detail']='.001*sin(u*20)'
        camera=copy.deepcopy(scene['camera']);camera[0]['eye']=[3,4,8]
        result, changed=revise_world(scene,[{'object_id':'sea','field':'bump_detail','value':None},
                                          {'field':'camera','value':camera}],{'a'*32})
        self.assertNotIn('bump_detail', result['objects'][0])
        self.assertEqual(result['camera'],camera)
        self.assertEqual(changed, sorted(changed))

    def test_equal_looking_invalid_types_cannot_hide_in_a_valid_batch(self):
        for field,value in [('emission',False),('segments',[96.0,64]),
                            ('position',{'x':False,'y':'0','z':'0'})]:
            edits=[{'field':'title','value':'A valid change'},
                   {'object_id':'sea','field':field,'value':value}]
            with self.subTest(field=field), self.assertRaises(SceneError):
                revise_world(world(),edits,{'a'*32})

    def test_handler_persists_new_plan_and_rejects_invalid_without_writes(self):
        base=Path(__file__).resolve().parents[1]/'.local/tests';base.mkdir(parents=True,exist_ok=True)
        with tempfile.TemporaryDirectory(dir=base) as tmp:
            root=Path(tmp);src=root/'input';src.mkdir();(src/'old.tga').write_bytes(fixture())
            projects=ProjectStore(root/'projects');p=projects.inspect(src);pid=p['project_id'];aid=p['assets'][0]['asset_id']
            store=CompositionStore(projects);parent=store.save_plan(pid,world(aid),[aid],{'origin':'test'})
            directory=projects._project(pid)/'plans';original=(directory/(parent['plan_id']+'.json')).read_bytes()
            handler=plugin.handlers.make_handlers(lambda:projects)['rekindra_revise_world']
            args={'project_id':pid,'plan_id':parent['plan_id'],'edits':[{'object_id':'sea','field':'roughness','value':.8}]}
            response=json.loads(handler(args));self.assertTrue(response['ok'],response)
            result=response['result'];self.assertEqual(result['parent_plan_id'],parent['plan_id'])
            revised=store.load_plan(pid,result['plan_id'])
            self.assertEqual(revised['source_ids'],parent['source_ids'])
            self.assertEqual(revised['scene']['objects'][0]['roughness'],.8)
            self.assertEqual((directory/(parent['plan_id']+'.json')).read_bytes(),original)
            before=set(directory.iterdir());args['edits']=[{'field':'title','value':'Should not persist'},
                                                        {'object_id':'sea','field':'roughness','value':9}]
            self.assertFalse(json.loads(handler(args))['ok'])
            self.assertEqual(set(directory.iterdir()),before)
