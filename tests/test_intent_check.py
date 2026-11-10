"""Intent check: notes that ask for a renderer feature the scene leaves off."""
import copy
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from rekindra_core.intent_check import intent_check  # noqa: E402


def plan(reason='A quiet street at dusk.', **scene_extra):
    scene = {'schema_version': 2, 'title': 'Evening', 'mood': 'calm', 'reason': reason,
             'references': [{'asset_id': 'a1', 'observed': 'a tree by a lamp', 'created': 'a lamp post'}],
             'environment': {'fog_density': .01},
             'objects': [{'id': 'ground', 'color': '#556677', 'color_high': '#8899aa', 'color_mix': '0.5'}]}
    scene.update(scene_extra)
    return {'scene': scene}


class IntentCheckTests(unittest.TestCase):
    def test_flagged_when_words_present_and_feature_absent(self):
        out = intent_check(plan('Soft glow halos fading into fog under a birch canopy.'))
        self.assertEqual([r['feature'] for r in out], ['atmosphere', 'foliage'])
        self.assertEqual(out[0]['stated'], 'glow, halos, fog')
        self.assertIn('scene.environment.atmosphere', out[0]['hint'])
        self.assertIn("'glow'", out[0]['hint'])
        self.assertEqual(out[1]['stated'], 'canopy, birch')
        self.assertEqual(out, intent_check(plan('Soft glow halos fading into fog under a birch canopy.')))

    def test_created_and_interpretations_are_read(self):
        p = plan()
        p['scene']['references'][0]['created'] = 'a feathered wispy figure'
        p['text_provenance'] = {'interpretations': [{'interpretation': 'cobble pavement, worn'}]}
        self.assertEqual([r['feature'] for r in intent_check(p)], ['soft', 'material_image'])

    def test_observed_is_not_intent(self):
        self.assertEqual(intent_check(plan()), [])

    def test_not_flagged_when_feature_present(self):
        p = plan('Glowing mist among the leaves; feathered figure; bark texture.')
        p['scene']['environment']['atmosphere'] = {'bloom': .6}
        p['scene']['objects'][0].update(foliage={}, soft={}, material_image={})
        self.assertEqual(intent_check(p), [])

    def test_no_notes_nothing(self):
        p = plan('')
        p['scene'].update(title='', mood='', references=[])
        self.assertEqual(intent_check(p), [])
        self.assertEqual(intent_check({}), [])

    def test_black_glow_flagged(self):
        p = plan()
        p['scene']['objects'].append({'id': 'lamp', 'glow': 1, 'color': '#ffcc88', 'color_high': '#000000', 'color_mix': '1'})
        p['scene']['objects'].append({'id': 'moon', 'glow': 1, 'color': '#000000', 'color_high': '#ffffff', 'color_mix': 0})
        p['scene']['objects'].append({'id': 'ok', 'glow': 1, 'color': '#000000', 'color_high': '#ffffff', 'color_mix': '1'})
        p['scene']['objects'].append({'id': 'varying', 'glow': 1, 'color': '#000000', 'color_high': '#ffffff', 'color_mix': 'sin(t)'})
        out = intent_check(p)
        self.assertEqual([r['stated'] for r in out], ['lamp', 'moon'])
        self.assertEqual(out[0]['hint'], "glow surface 'lamp' renders black because its color resolves to #000000; "
                                         'set color to the light color.')

    def test_word_boundary(self):
        for text in ('A long street.', 'Leafy streets, foggier than expected.', 'Bushwick', 'Haloes? no: halogen'):
            self.assertEqual(intent_check(plan(text)), [], text)
        self.assertEqual(intent_check(plan('TREES and Soft-Edged shapes'))[0]['feature'], 'foliage')
        self.assertEqual([r['feature'] for r in intent_check(plan('soft  edge'))], ['soft'])

    def test_does_not_mutate(self):
        p = plan('glow')
        before = copy.deepcopy(p)
        intent_check(p)
        self.assertEqual(p, before)


if __name__ == '__main__':
    unittest.main()
