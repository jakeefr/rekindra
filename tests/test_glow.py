import unittest
from test_worlds import world
from rekindra_core.worlds import validate_world, WORLD_SCHEMA
from rekindra_core.scenes import SceneError

class GlowTests(unittest.TestCase):
    def test_glow_is_optional_bounded_number(self):
        s=world();validate_world(s,{'a'*32})
        for value in (.05,1,3):
            s['objects'][0]['glow']=value
            self.assertEqual(validate_world(s,{'a'*32})['objects'][0]['glow'],value)
        for value in (None,True,0,.04,3.01,'1',[],float('nan')):
            s['objects'][0]['glow']=value
            with self.subTest(value=value),self.assertRaises(SceneError):validate_world(s,{'a'*32})
        self.assertIn('glow',WORLD_SCHEMA['properties']['objects']['items']['properties'])
    def test_glow_surface_cannot_be_reflector(self):
        s=world();o=s['objects'][0];o['position']['y']='0';o['reflection']=dict(strength=.5,blur=2)
        validate_world(s,{'a'*32})
        o['glow']=1
        with self.assertRaises(SceneError):validate_world(s,{'a'*32})
    def test_revision_sets_and_removes_glow_without_mutation(self):
        from rekindra_core.revisions import revise_world
        s=world();edit={'object_id':'sea','field':'glow','value':1.2}
        changed,_=revise_world(s,[edit],{'a'*32})
        self.assertNotIn('glow',s['objects'][0])
        self.assertEqual(changed['objects'][0]['glow'],1.2)
        reset,_=revise_world(changed,[dict(edit,value=None)],{'a'*32})
        self.assertEqual(reset,s)
