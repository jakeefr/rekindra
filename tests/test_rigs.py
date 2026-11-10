from pathlib import Path
import subprocess
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from rekindra_core.rigs import ANCHORS, POSES, solve_rig
from rekindra_core.scenes import SceneError
from rekindra_core.worlds import WORLD_SCHEMA, compile_surface, compile_world, validate_world

ROOT = Path(__file__).resolve().parents[1]


def surface(name, **fields):
    obj = {'id': name, 'position': {'x': '0', 'y': '0', 'z': '0'}, 'segments': [24, 12], 'color': '#888888',
           'color_high': '#aaaaaa', 'color_mix': '0', 'roughness': .7, 'metalness': 0, 'emission': 0}
    obj.update(fields)
    return obj


def world(objects, rigs=None):
    scene = {'schema_version': 2, 'title': 'Rig', 'mood': 'quiet', 'reason': 'A posed body built from geometry.',
             'duration': 12, 'width': 1280, 'height': 720, 'seed': 1, 'references': [{'asset_id': 'x', 'observed': 'Palette only.', 'created': 'Everything is invented geometry.'}],
             'environment': {'sky_top': '#1a2233', 'sky_bottom': '#8a8f9c', 'fog_color': '#8a8f9c', 'fog_density': .03,
                             'light_color': '#fff0d8', 'light_direction': [-.4, .7, .5], 'sun_size': .03, 'sun_strength': 1.6},
             'camera': [{'at': 0, 'eye': [1.2, 1.3, 5.2], 'target': [0, 1, 0], 'fov': 42},
                        {'at': 12, 'eye': [-.8, 1.2, 4.6], 'target': [0, 1, 0], 'fov': 42}],
             'objects': [surface('ground', position={'x': '(u-.5)*40', 'y': '0', 'z': '(v-.5)*40'}, segments=[8, 8])] + objects}
    if rigs is not None:
        scene['rigs'] = rigs
    return scene


RIG = {'id': 'a', 'position': [0, 0, 0], 'height': 1.8, 'pose': ['kneeling', 'arms_at_chest']}
FIGURE = dict(position={'x': 'figure_x', 'y': 'figure_y', 'z': 'figure_z'}, segments=[96, 16], figure={'rig': 'a'})
WING = dict(position={'x': 'wing_x', 'y': 'wing_y', 'z': 'wing_z'}, segments=[90, 12],
            wing={'span': 1.3, 'side': 'right', 'open': 'clamp((t-1)/8,0,1)'}, mount={'rig': 'a', 'anchor': 'back'})
RING = dict(position={'x': 'ring_x', 'y': 'ring_y', 'z': 'ring_z'}, segments=[48, 12],
            ring={'radius': .2, 'thickness': .02}, mount={'rig': 'a', 'anchor': 'head_top'})
DRAPE = dict(position={'x': 'drape_x', 'y': 'drape_y', 'z': 'drape_z'}, segments=[64, 32],
             drape={'top_radius': .2, 'hem_radius': .55, 'folds': 8, 'fold_depth': .14}, mount={'rig': 'a', 'anchor': 'hips'})


class SolverTests(unittest.TestCase):
    def test_every_pose_rests_on_the_ground_and_keeps_the_head_above_the_hips(self):
        for pose in POSES:
            rig = solve_rig({'id': 'a', 'position': [2, 1, -3], 'height': 1.8, 'pose': pose})
            self.assertEqual(set(rig['anchors']), set(ANCHORS), pose)
            low = min(min(b['a'][1] - b['ra'], b['a'][1] + b['d'][1] - b['rb']) for b in rig['bones'])
            self.assertAlmostEqual(low, 1, places=2, msg=pose)
            self.assertGreater(rig['anchors']['head_top'][1], rig['anchors']['hips'][1], pose)

    def test_kneeling_and_sitting_are_lower_than_standing_and_marked_seated(self):
        top = lambda pose: solve_rig({'id': 'a', 'position': [0, 0, 0], 'height': 1.8, 'pose': pose})
        self.assertAlmostEqual(top('standing')['anchors']['head_top'][1], 1.8, delta=.08)
        for pose in ('kneeling', 'sitting'):
            self.assertLess(top(pose)['anchors']['head_top'][1], 1.5)
            self.assertTrue(top(pose)['seated'])
        self.assertFalse(top('standing')['seated'])

    def test_joints_and_proportions_adjust_the_pose(self):
        base = solve_rig({'id': 'a', 'position': [0, 0, 0], 'height': 1.8})
        raised = solve_rig({'id': 'a', 'position': [0, 0, 0], 'height': 1.8, 'joints': {'shoulder_left': [3, 0, 0]}})
        self.assertGreater(raised['anchors']['hand_left'][1], base['anchors']['hand_left'][1] + .5)
        long_neck = solve_rig({'id': 'a', 'position': [0, 0, 0], 'height': 1.8, 'proportions': {'neck': 2.5}})
        gap = lambda r: r['anchors']['head_top'][1] - r['anchors']['shoulders'][1]
        self.assertGreater(gap(long_neck), gap(base))

    def test_bad_rigs_are_refused(self):
        for bad in ({'id': 'a', 'position': [0, 0, 0], 'height': 1.8, 'pose': 'flying'},
                    {'id': 'a', 'position': [0, 0, 0], 'height': 1.8, 'joints': {'tail': [0, 0, 0]}},
                    {'id': 'a', 'position': [0, 0, 0]}):
            with self.assertRaises(SceneError):
                solve_rig(bad)


class WorldTests(unittest.TestCase):
    def full(self):
        return world([surface('body', **FIGURE), surface('wing', **WING), surface('halo', **RING), surface('robe', **DRAPE)], [RIG])

    def test_a_posed_winged_figure_validates_and_compiles(self):
        scene = validate_world(self.full(), ['x'])
        compiled = compile_world(scene)
        ground, body, wing, halo, robe = compiled
        self.assertEqual(body['cards'], 16)
        self.assertEqual(wing['cards'], 30)
        self.assertNotIn('cards', ground)
        self.assertNotIn('rk_ml', str(ground))
        self.assertIn('rk_ml', str(halo))
        self.assertIn('rk_ml', str(robe))

    def test_mounted_drape_pools_only_under_a_seated_pose(self):
        seated = str(compile_world(validate_world(self.full(), ['x'])))
        standing = self.full(); standing['rigs'] = [dict(RIG, pose='standing')]
        self.assertNotEqual(seated, str(compile_world(validate_world(standing, ['x']))))
        kneel = solve_rig(RIG)
        self.assertTrue(kneel['seated'])

    def test_figure_and_mount_need_a_known_rig(self):
        for objects, rigs in (([surface('body', **FIGURE)], None),
                              ([surface('halo', **RING)], [dict(RIG, id='b')]),
                              ([surface('halo', **dict(RING, mount={'rig': 'a', 'anchor': 'tail'}))], [RIG])):
            with self.assertRaises(SceneError):
                validate_world(world(objects, rigs), ['x'])

    def test_scenes_without_rigs_compile_exactly_as_before(self):
        drape = dict(DRAPE); del drape['mount']; drape['drape'] = dict(drape['drape'], height=2)
        ring = dict(RING); del ring['mount']
        for fields in (drape, ring):
            obj = surface('part', **fields)
            self.assertEqual(compile_surface(obj), compile_surface(obj, None))
            text = str(compile_surface(obj))
            self.assertNotIn('rk_ml', text)
            self.assertNotIn('cards', compile_surface(obj))
        pooled = dict(drape, drape=dict(drape['drape'], pool=.3))
        rippled = dict(drape, drape=dict(drape['drape'], pool=.3, ripples=3))
        self.assertNotEqual(str(compile_surface(surface('p', **pooled))), str(compile_surface(surface('p', **rippled))))

    def test_schema_lists_the_new_fields_as_optional(self):
        self.assertNotIn('rigs', WORLD_SCHEMA.get('required', ['x']))
        item = WORLD_SCHEMA['properties']['objects']['items']
        for name in ('figure', 'wing', 'mount'):
            self.assertIn(name, item['properties'])
            self.assertNotIn(name, item.get('required', ['x']))

    def test_drape_and_ring_output_is_unchanged_from_the_previous_release(self):
        # The unmounted, unrippled text must match what the commit before rigs produced.
        script = ("import sys,json;sys.path.insert(0,'.');from rekindra_core.worlds import compile_surface;"
                  "o=lambda **k:dict({'id':'p','position':{'x':'drape_x','y':'drape_y','z':'drape_z'},'segments':[64,32],'color_mix':'0'},**k);"
                  "print(json.dumps([compile_surface(o(drape={'height':2,'top_radius':.2,'hem_radius':1,'folds':6,'fold_depth':.1,'pool':.3})),"
                  "compile_surface(o(position={'x':'feather_x','y':'feather_y','z':'feather_z'},segments=[36,8],feathers={'count':12,'spread':3,'length':1.2}))],sort_keys=True))")
        now = subprocess.run([sys.executable, '-c', script], cwd=ROOT, capture_output=True, text=True, check=True).stdout
        self.assertIn('rk_', now)
        self.assertNotIn('rk_ml', now)
        self.assertNotIn('"cards"', now)


if __name__ == '__main__':
    unittest.main()
