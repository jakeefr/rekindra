import unittest
from test_worlds import world
from rekindra_core.worlds import validate_world, WORLD_SCHEMA
from rekindra_core.scenes import SceneError

class ContactDepthTests(unittest.TestCase):
    def test_optional_contact_controls(self):
        s=world();s['environment'].update(occlusion_strength=.7,occlusion_radius=1.2)
        self.assertEqual(validate_world(s,{'a'*32}),s)
        self.assertIn('occlusion_strength',WORLD_SCHEMA['properties']['environment']['properties'])
        s['environment']['occlusion_strength']=0
        self.assertEqual(validate_world(s,{'a'*32}),s)

    def test_invalid_contact_controls(self):
        for key,values in [('occlusion_strength',[-.01,1.01,True,float('nan'),float('inf'),'1']),('occlusion_radius',[0,.049,4.01,True,float('nan'),None])]:
            for value in values:
                with self.subTest(key=key,value=value):
                    s=world();s['environment'][key]=value
                    with self.assertRaises(SceneError):validate_world(s,{'a'*32})
