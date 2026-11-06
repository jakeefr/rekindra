import unittest
from test_worlds import world
from rekindra_core.worlds import validate_world, WORLD_SCHEMA
from rekindra_core.scenes import SceneError


class CameraCutTests(unittest.TestCase):
    def test_cut_skips_nonexistent_crossing_path_but_keeps_endpoint_checks(self):
        s=world();s['camera'][0].update(eye=[0,0,4],target=[0,0,0])
        s['camera'][1].update(eye=[0,0,-4],target=[0,0,0],cut=True)
        self.assertTrue(validate_world(s,{'a'*32})['camera'][1]['cut'])
        s['camera'][1]['cut']=False
        with self.assertRaisesRegex(SceneError,'crosses'):validate_world(s,{'a'*32})
        s['camera'][1].update(cut=True,eye=[0,0,0])
        with self.assertRaisesRegex(SceneError,'distinct'):validate_world(s,{'a'*32})

    def test_cut_is_optional_strict_boolean_not_allowed_on_first_key(self):
        s=world();s['camera'][1]['cut']=False
        self.assertEqual(validate_world(s,{'a'*32}),s)
        self.assertEqual(WORLD_SCHEMA['properties']['camera']['items']['properties']['cut']['type'],'boolean')
        for invalid in (0,1,'true',None,[]):
            s['camera'][1]['cut']=invalid
            with self.assertRaises(SceneError):validate_world(s,{'a'*32})
        s=world();s['camera'][0]['cut']=True
        with self.assertRaisesRegex(SceneError,'first'):validate_world(s,{'a'*32})
