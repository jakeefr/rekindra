import copy
import math
import unittest
from test_worlds import world
from rekindra_core.worlds import validate_world, WORLD_SCHEMA
from rekindra_core.scenes import SceneError


def panel():
    return dict(direction=[-1, 2, 3], color='#FFF4DF', intensity=3,
                size=[.12, .6], rotation=0)


class EnvironmentPanelTests(unittest.TestCase):
    def test_optional_bounded_contract(self):
        s=world(); original=copy.deepcopy(s)
        self.assertEqual(validate_world(s, {'a'*32}), original)
        s['environment']['environment_panels']=[panel()]*4
        self.assertEqual(validate_world(s, {'a'*32}), s)
        schema=WORLD_SCHEMA['properties']['environment']['properties']['environment_panels']
        self.assertEqual(schema['maxItems'], 4)
        self.assertNotIn('environment_panels', WORLD_SCHEMA['properties']['environment']['required'])
        s['environment']['environment_panels']=[]
        validate_world(s, {'a'*32})

    def test_rejects_invalid_and_unbounded_panels(self):
        invalid=[None, {}, [panel()]*5]
        for key, values in {
            'direction': [[0,0,0], [1,2], [True,1,1], [math.nan,1,1]],
            'size': [[0,.3], [.3,2], [.3], 'wide', [True,.3]],
            'intensity': [-1,17,True,math.inf],
            'rotation': [7,False,math.nan], 'color': ['white'],
        }.items():
            for value in values:
                p=panel();p[key]=value;invalid.append([p])
        p=panel();p['extra']=1;invalid.append([p])
        p=panel();del p['rotation'];invalid.append([p])
        for value in invalid:
            with self.subTest(value=value):
                s=world();s['environment']['environment_panels']=value
                with self.assertRaises(SceneError):validate_world(s, {'a'*32})
