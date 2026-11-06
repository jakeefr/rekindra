import unittest
from test_worlds import world
from rekindra_core.worlds import validate_world
from rekindra_core.scenes import SceneError

class FlatShadingTests(unittest.TestCase):
    def test_revision_sets_and_removes_shading_without_mutation(self):
        from rekindra_core.revisions import revise_world
        s=world();edit={'object_id':'sea','field':'shading','value':'flat'}
        changed,_=revise_world(s,[edit],{'a'*32})
        self.assertNotIn('shading',s['objects'][0])
        self.assertEqual(changed['objects'][0]['shading'],'flat')
        reset,_=revise_world(changed,[dict(edit,value=None)],{'a'*32})
        self.assertEqual(reset,s)
    def test_shading_is_optional_bounded_enum(self):
        s=world();validate_world(s,{'a'*32})
        for value in ('smooth','flat'):
            s['objects'][0]['shading']=value
            self.assertEqual(validate_world(s,{'a'*32})['objects'][0]['shading'],value)
        for value in (None,True,0,[],{},'Flat',''):
            s['objects'][0]['shading']=value
            with self.subTest(value=value),self.assertRaises(SceneError):validate_world(s,{'a'*32})
