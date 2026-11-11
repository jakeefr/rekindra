from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from rekindra_core.constructs import collect_adjustments, compile_constructs
from rekindra_core.scenes import SceneError
from rekindra_core.worlds import compile_surface, WORLD_SCHEMA


def surface(**fields):
    obj = {'id': 'part', 'position': {'x': '0', 'y': '0', 'z': '0'}, 'segments': [24, 12], 'color_mix': '0'}
    obj.update(fields)
    return obj


class DefaultOffTests(unittest.TestCase):
    def test_a_surface_without_construction_fields_compiles_nothing_extra(self):
        self.assertEqual(compile_constructs(surface()), [])
        self.assertNotIn('rk_feather', str(compile_surface(surface())))

    def test_one_construction_field_per_surface(self):
        both = surface(ring={'radius': 1, 'thickness': .1}, drape={'height': 2, 'top_radius': .2, 'hem_radius': 1})
        with self.assertRaisesRegex(SceneError, 'one construction field'):
            compile_constructs(both)

    def test_schema_lists_each_field_as_optional(self):
        item = WORLD_SCHEMA['properties']['objects']['items']
        for name in ('feathers', 'drape', 'ring'):
            self.assertIn(name, item['properties'])
            self.assertNotIn(name, item.get('required', []))
            self.assertIn('glow and soft', item['properties'][name]['description'])


class FeatherTests(unittest.TestCase):
    SPEC = {'count': 12, 'spread': 3, 'length': 1.2, 'curve': .8, 'fan': 1.1, 'taper': .5, 'overlap': .6,
            'open': 'clamp(t/8,0,1)', 'mirror': True}

    def test_supplies_feather_coordinates_to_position(self):
        out = compile_surface(surface(feathers=self.SPEC, position={'x': 'feather_x+1', 'y': 'feather_y+2', 'z': 'feather_z'}))
        text = str(out)
        self.assertIn('rk_feather_p.x', text)
        self.assertIn('rk_feather_p.y', text)

    def test_open_is_an_expression_over_time_and_mirror_flips_x(self):
        part = compile_constructs(surface(feathers=self.SPEC))[0]
        self.assertRegex(part['definitions'], r'rk_fo=clamp\(.*t.*\)')
        self.assertIn('vec3(-rk_fq.x', part['definitions'])
        still = compile_constructs(surface(feathers={'count': 12, 'spread': 3, 'length': 1}))[0]
        self.assertIn('vec3(rk_fq.x', still['definitions'])
        self.assertGreater(part['cost'], still['cost'] - 1)

    def test_segments_that_do_not_divide_into_cards_snap_to_the_nearest_count_and_say_so(self):
        for given in (20, 12, 30):   # 30 sits between 24 and 36: the higher count wins a tie
            part = surface(feathers=self.SPEC, segments=[given, 6])
            with collect_adjustments() as notes:
                compile_constructs(part)
            self.assertEqual(part['segments'], [36 if given == 30 else 24, 6], given)
            self.assertEqual(len(notes), 1)
            self.assertIn(f'surface part: feathers u segments {given} ', notes[0])
            self.assertIn(f'used {part["segments"][0]}', notes[0])
        fits = surface(feathers=self.SPEC, segments=[24, 6])
        with collect_adjustments() as notes:
            compile_constructs(fits)
        self.assertEqual((fits['segments'], notes), ([24, 6], []))
        compile_constructs(surface(feathers=self.SPEC, segments=[20, 6]))   # no collector: still snaps, no error

    def test_malformed_segments_are_still_refused(self):
        with self.assertRaises(SceneError):
            compile_constructs(surface(feathers=dict(self.SPEC, count=48), segments=['many', 6]))

    def test_bad_values_are_refused(self):
        for bad in ({'count': 1}, {'count': 49}, {'count': 2.5}, {'overlap': 2}, {'mirror': 1}, {'colour': 1}, {'open': 'import os'}):
            with self.assertRaises(SceneError, msg=bad):
                compile_constructs(surface(feathers=dict(self.SPEC, **bad)))


class DrapeTests(unittest.TestCase):
    SPEC = {'height': 2.2, 'top_radius': .25, 'hem_radius': 1.1, 'pool': .6, 'folds': 9, 'fold_depth': .15}

    def test_supplies_drape_coordinates_with_folds_and_a_pooled_hem(self):
        text = str(compile_surface(surface(drape=self.SPEC, position={'x': 'drape_x', 'y': 'drape_y', 'z': 'drape_z-3'})))
        self.assertIn('rk_drape_p.x', text)
        part = compile_constructs(surface(drape=self.SPEC))[0]
        self.assertIn('cos(9.*rk_da)', part['definitions'])
        self.assertIn('rk_dv/.85', part['definitions'])
        hanging = compile_constructs(surface(drape={'height': 2, 'top_radius': .2, 'hem_radius': 1}))[0]
        self.assertIn('rk_dv/1.', hanging['definitions'])

    def test_bad_values_are_refused(self):
        for bad in ({'height': 0}, {'folds': 2.5}, {'fold_depth': 1}, {'pool': -1}, {'extra': 1}):
            with self.assertRaises(SceneError, msg=bad):
                compile_constructs(surface(drape=dict(self.SPEC, **bad)))


class RingTests(unittest.TestCase):
    def test_supplies_ring_coordinates_and_tilts(self):
        text = str(compile_surface(surface(ring={'radius': .5, 'thickness': .04, 'tilt': 1.5708},
                                           position={'x': 'ring_x', 'y': 'ring_y+3', 'z': 'ring_z'})))
        self.assertIn('rk_ring_p.y', text)
        flat = compile_constructs(surface(ring={'radius': .5, 'thickness': .04}))[0]['definitions']
        tilted = compile_constructs(surface(ring={'radius': .5, 'thickness': .04, 'tilt': 1.5708}))[0]['definitions']
        self.assertNotEqual(flat, tilted)

    def test_bad_values_are_refused(self):
        for bad in ({'radius': .1, 'thickness': .2}, {'radius': 0, 'thickness': .01}, {'radius': 1, 'thickness': .1, 'tilt': 9},
                    {'radius': 1}):
            with self.assertRaises(SceneError, msg=bad):
                compile_constructs(surface(ring=bad))


if __name__ == '__main__':
    unittest.main()
