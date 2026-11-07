import copy
import unittest
from test_worlds import world
from rekindra_core.worlds import validate_world, compile_world, WORLD_SCHEMA
from rekindra_core.revisions import revise_world
from rekindra_core.scenes import SceneError


class ColorPatternTests(unittest.TestCase):
    def test_compiles_and_revises_without_mutating_original(self):
        original = world()
        pattern = '.5+.5*cos(u*8*pi+t)'
        scene, paths = revise_world(original, [{'object_id': 'sea', 'field': 'color_pattern', 'value': pattern}], {'a'*32})
        self.assertNotIn('color_pattern', original['objects'][0])
        self.assertIn('cos', compile_world(scene)[0]['color_pattern'])
        self.assertEqual(paths, ['objects/sea/color_pattern'])
        restored, _ = revise_world(scene, [{'object_id': 'sea', 'field': 'color_pattern', 'value': None}], {'a'*32})
        self.assertEqual(restored, original)
        self.assertNotIn('color_pattern', compile_world(original)[0])
        self.assertIn('color_pattern', WORLD_SCHEMA['properties']['objects']['items']['properties'])

    def test_rejects_executable_input_bindings_and_unbounded_work(self):
        for value in ('shape', '__import__("os")', '+'.join(['u']*20), 'u'*129, '', 1):
            with self.subTest(value=value):
                scene = world()
                scene['objects'][0]['bindings'] = [{'name': 'shape', 'expression': 'u*2'}]
                scene['objects'][0]['color_pattern'] = value
                with self.assertRaises(SceneError):
                    validate_world(scene, {'a'*32})

    def test_pattern_shares_world_fragment_budget(self):
        scene = world()
        obj = scene['objects'][0]
        obj['segments'] = [4, 4]
        obj['color_pattern'] = '+'.join(['u']*15)
        obj['bump_detail'] = '+'.join(['v']*15)
        scene['objects'] = [dict(copy.deepcopy(obj), id=f's{i}') for i in range(3)]
        with self.assertRaisesRegex(SceneError, '128 total'):
            validate_world(scene, {'a'*32})

    def test_refuses_high_frequency_stripes(self):
        # B01 architecture study: this payload rendered conspicuous radial terrace stripes.
        # Patterns are clamped 0..1 like the renderer's blend, so a band around .5 counts,
        # and stripes that only appear later in time are sampled too.
        for value in ('.35+.25*cos(u*80*pi)', '.2*sin(v*120)', 'clamp(sin(u*200),-.2,.2)',
                      '.5+.1*cos(u*80*pi)', '.7+.2*sin(u*200)', '.5+.4*sin(u*200*t)'):
            with self.subTest(value=value):
                scene = world()
                scene['objects'][0]['color_pattern'] = value
                with self.assertRaisesRegex(SceneError, 'stripes'):
                    validate_world(scene, {'a'*32})
        # Low-frequency bands and fine grain with a small swing remain allowed.
        for value in ('.5+.5*cos(u*8*pi+t)', 'clamp(.5+2*sin(2*pi*u),0,1)', '.03*sin(u*170+v*45)',
                      '.48+.035*sin(u*170+v*45-t*.85)', '-.4+.2*sin(u*200)', '1.5+.3*sin(v*300)'):
            with self.subTest(value=value):
                scene = world()
                scene['objects'][0]['color_pattern'] = value
                validate_world(scene, {'a'*32})
