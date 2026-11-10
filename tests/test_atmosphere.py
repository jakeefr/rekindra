import copy
import math
import unittest
from pathlib import Path
from test_worlds import world
from rekindra_core.worlds import validate_world, WORLD_SCHEMA, ATMOSPHERE_RANGES
from rekindra_core.scenes import SceneError

RUNTIME = Path(__file__).resolve().parents[1] / 'runtime'


def atmosphere():
    return dict(bloom=.9, halo=1, haze_density=.012, haze_color='#1E2329',
                haze_height=5, haze_floor=0, vignette=.35, grain=.02)


class AtmosphereTests(unittest.TestCase):
    def test_optional_and_off_by_default(self):
        s = world(); original = copy.deepcopy(s)
        self.assertNotIn('atmosphere', s['environment'])
        self.assertEqual(validate_world(s, {'a' * 32}), original)
        s['environment']['atmosphere'] = atmosphere()
        self.assertEqual(validate_world(s, {'a' * 32}), s)
        env = WORLD_SCHEMA['properties']['environment']
        self.assertNotIn('atmosphere', env['required'])
        schema = env['properties']['atmosphere']
        self.assertFalse(schema['additionalProperties'])
        self.assertEqual(set(schema['properties']),
                         {k for k, _, _ in ATMOSPHERE_RANGES} | {'haze_color', 'highlights'})

    def test_each_field_alone_is_enough(self):
        for key, value in atmosphere().items():
            with self.subTest(key=key):
                s = world(); s['environment']['atmosphere'] = {key: value}
                validate_world(s, {'a' * 32})

    def test_soft_highlights_is_the_only_highlight_option(self):
        s = world(); s['environment']['atmosphere'] = {'highlights': 'soft'}
        self.assertEqual(validate_world(s, {'a' * 32})['environment']['atmosphere'], {'highlights': 'soft'})
        for value in ('off', 'hard', '', None, True, 1, ['soft']):
            with self.subTest(value=value):
                s = world(); s['environment']['atmosphere'] = {'bloom': .5, 'highlights': value}
                with self.assertRaises(SceneError):
                    validate_world(s, {'a' * 32})
        schema = WORLD_SCHEMA['properties']['environment']['properties']['atmosphere']['properties']['highlights']
        self.assertEqual(schema['enum'], ['soft'])

    def test_runtime_emits_soft_tone_only_when_asked(self):
        source = (RUNTIME / 'world.js').read_text(encoding='utf-8')
        self.assertIn("softHighlights=atmo?.highlights==='soft'", source)

    def test_rejects_empty_unknown_and_out_of_range(self):
        invalid = [None, {}, [], 'fog', {'glow': 1}]
        for key, low, high in ATMOSPHERE_RANGES:
            for value in (low - 1, high + 1, True, math.nan, 'much'):
                invalid.append({key: value})
        invalid.append({'haze_color': 'grey'})
        for value in invalid:
            with self.subTest(value=value):
                s = world(); s['environment']['atmosphere'] = value
                with self.assertRaises(SceneError):
                    validate_world(s, {'a' * 32})

    def test_runtime_gates_the_pass_on_the_scene_field(self):
        source = (RUNTIME / 'world.js').read_text(encoding='utf-8')
        self.assertIn('const atmo=scene.environment.atmosphere', source)
        self.assertIn('if(post)atmospherePass(c,b,time)', source)
        self.assertIn('if(atmo){', source)
        player = (RUNTIME / 'player.js').read_text(encoding='utf-8')
        # Review frames are compared for motion, so grain must be off while they render.
        self.assertIn('world.setGrain(false)', player)
        self.assertIn('world.setGrain(true)', player)


if __name__ == '__main__':
    unittest.main()
