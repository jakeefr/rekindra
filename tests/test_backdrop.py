"""Warn, never reject, when the camera path can see the end of wide scenery."""
import copy
import unittest
from importlib import import_module

from test_plugin import plugin

backdrop = import_module(f'{plugin.__name__}.rekindra_core.backdrop')

ANGLED = {'eye': [15, 10, 24], 'target': [.4, 3, 0], 'fov': 44}
HEAD_ON = {'eye': [0, 10, 24], 'target': [0, 3, 0], 'fov': 44}


def ribbon(identifier='hills', x='(u-0.5)*180', z='-32', **extra):
    return {'id': identifier, 'position': {'x': x, 'y': 'v*20', 'z': z}, **extra}


def world(objects, first=ANGLED, last=None, fog=.002):
    return {'schema_version': 2, 'duration': 8, 'environment': {'fog_density': fog},
            'camera': [{'at': 0, **first}, {'at': 8, **(last or first)}], 'objects': objects}


class BackdropWarningTests(unittest.TestCase):
    def test_visible_end_warns_with_the_object_and_the_fixes(self):
        warnings = backdrop.backdrop_warnings(world([ribbon()]))
        self.assertEqual(len(warnings), 1)
        self.assertTrue(warnings[0].startswith('hills: its u=0 end is in frame at t=0.0s'))
        for fix in ('move it closer', 'widen it', 'more head-on'):
            self.assertIn(fix, warnings[0])

    def test_the_clamp_is_applied_before_projecting(self):
        wider_than_the_world = ribbon(x='(u-0.5)*400')
        self.assertEqual(len(backdrop.backdrop_warnings(world([wider_than_the_world]))), 1)

    def test_the_named_fixes_clear_it(self):
        self.assertEqual(backdrop.backdrop_warnings(world([ribbon()], first=HEAD_ON)), [])
        self.assertEqual(backdrop.backdrop_warnings(world([ribbon(z='-5')])), [])

    def test_the_whole_camera_path_counts(self):
        late = {'eye': [0, 10, 24], 'target': [-70, 3, 0], 'fov': 44}
        warnings = backdrop.backdrop_warnings(world([ribbon()], first=HEAD_ON, last=late))
        self.assertEqual(len(warnings), 1)
        self.assertNotIn('t=0.0s', warnings[0])

    def test_camera_cut_holds_the_earlier_shot(self):
        scene = world([ribbon()], first=HEAD_ON, last=ANGLED)
        scene['camera'][1]['cut'] = True
        scene['camera'].insert(1, {'at': 7, **HEAD_ON})
        self.assertIn('t=8.0s', backdrop.backdrop_warnings(scene)[0])

    def test_fog_can_hide_the_end(self):
        self.assertEqual(backdrop.backdrop_warnings(world([ribbon()], fog=.15)), [])

    def test_small_objects_are_not_scenery(self):
        self.assertEqual(backdrop.backdrop_warnings(world([ribbon(x='(u-0.5)*10')])), [])

    def test_a_ground_plane_horizon_is_not_an_end(self):
        plane = {'id': 'water', 'position': {'x': '(u-0.5)*180', 'y': '0', 'z': '(v-0.5)*180'}}
        self.assertEqual(backdrop.backdrop_warnings(world([plane], first=HEAD_ON)), [])

    def test_a_closed_ring_has_no_ends(self):
        ring = {'id': 'cyclorama', 'position': {'x': '90*sin(u*2*pi)', 'y': 'v*40', 'z': '90*cos(u*2*pi)'}}
        self.assertEqual(backdrop.backdrop_warnings(world([ring])), [])

    def test_bindings_and_a_single_instance_are_followed(self):
        bound = ribbon(x='w*0.2', bindings=[{'name': 'w', 'expression': '(u-0.5)*180'}],
                       instances=[{'offset': [0, 0, 0], 'scale': [5, 1, 1]}])
        self.assertEqual(len(backdrop.backdrop_warnings(world([bound]))), 1)

    def test_surfaces_it_cannot_model_are_skipped(self):
        rotated = ribbon(instances=[{'offset': [0, 0, 0], 'scale': [1, 1, 1], 'rotation': [0, .2, 0]}])
        assembled = ribbon('assembled', assembly='frame')
        self.assertEqual(backdrop.backdrop_warnings(world([rotated, assembled])), [])

    def test_a_bad_expression_costs_only_that_surface(self):
        broken = ribbon('broken', x='import_os(1)')
        self.assertEqual(len(backdrop.backdrop_warnings(world([broken, ribbon()]))), 1)

    def test_same_scene_same_warnings_and_scene_untouched(self):
        scene = world([ribbon(), ribbon('ridge', z='-40')])
        before = copy.deepcopy(scene)
        self.assertEqual(backdrop.backdrop_warnings(scene), backdrop.backdrop_warnings(scene))
        self.assertEqual(scene, before)

    def test_older_scenes_are_ignored(self):
        self.assertEqual(backdrop.backdrop_warnings({'schema_version': 1}), [])


if __name__ == '__main__':
    unittest.main()
