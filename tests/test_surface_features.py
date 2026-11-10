import copy
import unittest
from pathlib import Path
from test_worlds import world
from rekindra_core.worlds import validate_world, WORLD_SCHEMA
from rekindra_core.scenes import SceneError

RUNTIME = Path(__file__).resolve().parents[1] / 'runtime'
ASSET = 'a' * 32


def scene_with(**fields):
    s = world()
    for key in ('glow', 'reflection'):
        s['objects'][0].pop(key, None)
    s['objects'][0].update(fields)
    return s


class SurfaceFeatureTests(unittest.TestCase):
    def test_all_optional_and_off_by_default(self):
        s = world(); original = copy.deepcopy(s)
        for o in s['objects']:
            for key in ('soft', 'foliage', 'material_image'):
                self.assertNotIn(key, o)
        self.assertEqual(validate_world(s, {ASSET}), original)
        item = WORLD_SCHEMA['properties']['objects']['items']
        for key in ('soft', 'foliage', 'material_image'):
            self.assertNotIn(key, item['required'])
            self.assertFalse(item['properties'][key]['additionalProperties'])
        self.assertEqual(item['properties']['soft']['required'], ['u', 'v'])
        self.assertEqual(item['properties']['foliage']['required'], ['leaf_size', 'density'])
        self.assertEqual(item['properties']['material_image']['required'], ['asset_id', 'crop'])

    def test_accepts_each_feature(self):
        for fields in (
            {'glow': .8, 'soft': {'u': .5, 'v': .6}},
            {'glow': .8, 'soft': {'u': 1, 'v': 0, 'breakup': .7}},
            {'foliage': {'leaf_size': .2, 'density': .6}},
            {'foliage': {'leaf_size': .2, 'density': .6, 'variation': .8}},
            {'material_image': {'asset_id': ASSET, 'crop': [0, 0, 1, 1]}},
            {'material_image': {'asset_id': ASSET, 'crop': [.1, .2, .3, .4], 'repeat': [2, 6], 'strength': .5}},
            {'foliage': {'leaf_size': .2, 'density': .6},
             'material_image': {'asset_id': ASSET, 'crop': [.1, .2, .3, .4]}},
        ):
            with self.subTest(fields=fields):
                s = scene_with(**fields)
                self.assertEqual(validate_world(s, {ASSET}), s)

    def test_rejects_invalid_values(self):
        for fields in (
            {'soft': {'u': .5, 'v': .5}},                                  # soft needs glow
            {'glow': .8, 'soft': {'u': .5}},
            {'glow': .8, 'soft': {'u': 1.5, 'v': .5}},
            {'glow': .8, 'soft': {'u': .5, 'v': .5, 'blur': 1}},
            {'glow': .8, 'soft': 'yes'},
            {'foliage': {'leaf_size': .2}},
            {'foliage': {'leaf_size': 9, 'density': .6}},
            {'foliage': {'leaf_size': .2, 'density': .05}},
            {'foliage': {'leaf_size': .2, 'density': .6, 'variation': 2}},
            {'glow': .8, 'foliage': {'leaf_size': .2, 'density': .6}},     # leaves do not glow
            {'material_image': {'asset_id': ASSET}},
            {'material_image': {'asset_id': 'b' * 32, 'crop': [0, 0, 1, 1]}},   # not a source of this scene
            {'material_image': {'asset_id': ASSET, 'crop': [.5, 0, .6, 1]}},    # crop leaves the image
            {'material_image': {'asset_id': ASSET, 'crop': [0, 0, .001, 1]}},
            {'material_image': {'asset_id': ASSET, 'crop': [0, 0, 1]}},
            {'material_image': {'asset_id': ASSET, 'crop': [0, 0, 1, 1], 'repeat': [0, 1]}},
            {'material_image': {'asset_id': ASSET, 'crop': [0, 0, 1, 1], 'strength': 2}},
            {'material_image': {'asset_id': ASSET, 'crop': [0, 0, 1, 1], 'url': 'http://x'}},
        ):
            with self.subTest(fields=fields):
                with self.assertRaises(SceneError):
                    validate_world(scene_with(**fields), {ASSET})

    def test_runtime_gates_each_feature_on_its_field(self):
        source = (RUNTIME / 'world.js').read_text(encoding='utf-8')
        self.assertIn('const photo=o.material_image,soft=o.soft,leaf=o.foliage', source)
        self.assertIn("${photo?'uniform sampler2D materialImage;':''}", source)
        self.assertIn("${soft||leaf?featureNoise:''}", source)
        self.assertIn('images={}', source)
        player = (RUNTIME / 'player.js').read_text(encoding='utf-8')
        self.assertIn('Recovered material: surface', player)
        self.assertIn('The shape it covers is created.', player)


if __name__ == '__main__':
    unittest.main()
