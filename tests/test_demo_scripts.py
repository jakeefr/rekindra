import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np
from PIL import Image

SCRIPTS = Path(__file__).resolve().parents[1] / 'scripts'


def load(name):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / f'{name}.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


check = load('check_demo_scene')
export = load('export_acceptance_case')

EYES = [{'at': 0, 'eye': [12, 10, 24], 'target': [0, 3, 0], 'fov': 46}]
ENV = {'fog_density': .003, 'fog_color': '#B88198', 'sky_bottom': '#B88198'}


def two_sections(pts):
    return [{'height': 0, 'points': [[x * .8, z * .9] for x, z in pts]}, {'height': .3, 'points': pts}]


def water(position, **extra):
    return dict({'id': 'sea', 'position': position}, **extra)


class HorizonTests(unittest.TestCase):
    def scene(self, obj):
        return {'environment': ENV, 'camera': EYES, 'objects': [obj], 'assemblies': []}

    def test_centred_disc_with_rim_fade_passes(self):
        disc = water({'x': '12+320*v*v*cos(u*2*pi)', 'y': '0', 'z': '24+320*v*v*sin(u*2*pi)'},
                     color_high='#B88198', color_pattern='clamp((v-.9)*10,0,1)')
        ok, detail = check.check_horizon(self.scene(disc), 'sea')
        self.assertTrue(ok, detail)
        self.assertIn("sides=['v1']", detail)  # u seam and collapsed centre are not edges

    def test_small_square_fails(self):
        square = water({'x': '(u-.5)*100', 'y': '0', 'z': '(v-.5)*100'})
        ok, detail = check.check_horizon(self.scene(square), 'sea')
        self.assertFalse(ok, detail)

    def test_rim_fade_needs_pattern_near_one(self):
        disc = water({'x': '12+320*v*v*cos(u*2*pi)', 'y': '0', 'z': '24+320*v*v*sin(u*2*pi)'},
                     color_high='#B88198', color_pattern='clamp((v-.9)*5,0,1)')
        ok, detail = check.check_horizon(self.scene(disc), 'sea')
        self.assertFalse(ok, detail)  # pattern only reaches .5 at the rim

    def test_assembly_transform_is_reported_not_guessed(self):
        disc = water({'x': '320*v*v*cos(u*2*pi)', 'y': '0', 'z': '320*v*v*sin(u*2*pi)'}, assembly='drift')
        scene = self.scene(disc)
        scene['assemblies'] = [{'id': 'drift', 'translation': {'x': 't', 'y': '0', 'z': '0'},
                                'rotation': {'x': '0', 'y': '0', 'z': '0'}, 'pivot': [0, 0, 0], 'scale': [1, 1, 1]}]
        ok, detail = check.check_horizon(scene, 'sea')
        self.assertIsNone(ok)
        self.assertIn('unmeasured', detail)

    def test_parent_or_static_rotation_or_instance_rotation_is_unmeasured(self):
        base = {'id': 'drift', 'translation': {'x': '0', 'y': '0', 'z': '0'},
                'rotation': {'x': '0', 'y': '0', 'z': '0'}, 'pivot': [0, 0, 0], 'scale': [1, 1, 1]}
        disc = water({'x': '320*v*v*cos(u*2*pi)', 'y': '0', 'z': '320*v*v*sin(u*2*pi)'}, assembly='drift')
        for change in ({'parent': 'root'}, {'rotation': {'x': '0', 'y': '0.3', 'z': '0'}}):
            scene = self.scene(dict(disc))
            scene['assemblies'] = [dict(base, **change)]
            self.assertIsNone(check.check_horizon(scene, 'sea')[0], change)
        rotated = water(disc['position'], instances=[{'offset': [0, 0, 0], 'rotation': [0, .5, 0]}])
        self.assertIsNone(check.check_horizon(self.scene(rotated), 'sea')[0])

    def test_unsampleable_pattern(self):
        def disc(r):
            return water({'x': f'12+{r}*v*v*cos(u*2*pi)', 'y': '0', 'z': f'24+{r}*v*v*sin(u*2*pi)'},
                         color_high='#B88198', color_pattern='mystery(v)')
        self.assertIsNone(check.check_horizon(self.scene(disc(320)), 'sea')[0])
        self.assertFalse(check.check_horizon(self.scene(disc(120)), 'sea')[0])  # rim too near: FAIL anyway
        slanted = water({'x': '300+600*v*v*cos(u*2*pi)', 'y': '0', 'z': '600*v*v*sin(u*2*pi)'},
                        color_high='#B88198', color_pattern='mystery(v)')
        ok, detail = check.check_horizon(self.scene(slanted), 'sea')
        self.assertFalse(ok, detail)  # far but uneven rim: FAIL anyway
        self.assertIn('unsampled', detail)
        foggy = {'environment': dict(ENV, fog_density=.02), 'camera': EYES, 'objects': [disc(320)], 'assemblies': []}
        self.assertTrue(check.check_horizon(foggy, 'sea')[0])  # fog alone decides the fade

    def test_instance_scale_moves_the_rim(self):
        disc = water({'x': '12+150*v*v*cos(u*2*pi)', 'y': '0', 'z': '24+150*v*v*sin(u*2*pi)'},
                     color_high='#B88198', color_pattern='clamp((v-.9)*10,0,1)')
        self.assertFalse(check.check_horizon(self.scene(disc), 'sea')[0])  # rim ~150 from the eye
        big = dict(disc, position={'x': '150*v*v*cos(u*2*pi)', 'y': '0', 'z': '150*v*v*sin(u*2*pi)'},
                   instances=[{'offset': [12, 0, 24], 'scale': [2, 1, 2]}])
        ok, detail = check.check_horizon(self.scene(big), 'sea')
        self.assertTrue(ok, detail)


class BeamAndBoatTests(unittest.TestCase):
    def test_t_token(self):
        self.assertTrue(check.uses_t('-0.7+t*0.35'))
        for static in ('0', 'sqrt(2)', 'smoothstep(0,1,.5)', 'atan(1)', 'step(.5,.2)'):
            self.assertFalse(check.uses_t(static), static)

    def test_missing_beam_is_named(self):
        frames = [np.zeros((10, 10, 3))]
        ok, detail = check.check_beam({'objects': [], 'assemblies': []}, frames, 'beam')
        self.assertFalse(ok)
        self.assertIn('not found', detail)

    def test_beam_without_assembly_is_named(self):
        ok, detail = check.check_beam({'objects': [{'id': 'beam'}], 'assemblies': []}, [np.zeros((4, 4, 3))], 'beam')
        self.assertFalse(ok)
        self.assertIn('no assembly', detail)

    def test_pointed_loft_passes_and_disc_fails(self):
        pts = [[0, -1.4], [.32, -.7], [.45, .2], [.36, 1.0], [-.36, 1.0], [-.45, .2], [-.32, -.7]]
        hull = {'id': 'boat', 'assembly': 'home', 'loft': two_sections(pts),
                'position': {'x': 'loft_x', 'y': 'loft_y', 'z': 'loft_z'}}
        mast = {'id': 'mast', 'assembly': 'home'}
        ok, detail = check.check_boats({'objects': [hull, mast]}, 'boat')
        self.assertTrue(ok, detail)
        disc = {'id': 'boat', 'assembly': 'home',
                'position': {'x': '.6*v*cos(u*2*pi)', 'y': '0', 'z': '.4*v*sin(u*2*pi)'}}
        ok, detail = check.check_boats({'objects': [disc, mast]}, 'boat')
        self.assertFalse(ok, detail)

    def test_instance_scale_uses_least_elongated_copy(self):
        pts = [[0, -1.4], [.45, 0], [0, 1.4], [-.45, 0]]
        hull = {'id': 'boat', 'assembly': 'home', 'loft': two_sections(pts),
                'position': {'x': 'loft_x', 'y': 'loft_y', 'z': 'loft_z'},
                'instances': [{'offset': [0, 0, 0], 'scale': [1, 1, 1]}, {'offset': [3, 0, 0], 'scale': [2.5, 1, 1]}]}
        ok, detail = check.check_boats({'objects': [hull, {'id': 'mast', 'assembly': 'home'}]}, 'boat')
        self.assertFalse(ok, detail)  # the second copy is stretched almost square

    def test_deformed_loft_is_unmeasured_not_failed(self):
        pts = [[0, -1.4], [.45, 0], [0, 1.4], [-.45, 0]]
        hull = {'id': 'boat', 'assembly': 'home', 'loft': two_sections(pts),
                'position': {'x': 'loft_x*1.1', 'y': 'loft_y', 'z': 'loft_z'}}
        ok, detail = check.check_boats({'objects': [hull, {'id': 'mast', 'assembly': 'home'}]}, 'boat')
        self.assertIsNone(ok, detail)

    def test_assembly_scale_and_tilt(self):
        pts = [[0, -1.4], [.32, -.7], [.45, .2], [.36, 1.0], [-.36, 1.0], [-.45, .2], [-.32, -.7]]
        hull = {'id': 'boat', 'assembly': 'home', 'loft': two_sections(pts),
                'position': {'x': 'loft_x', 'y': 'loft_y', 'z': 'loft_z'}}
        objs = [hull, {'id': 'mast', 'assembly': 'home'}]
        flat = {'id': 'home', 'rotation': {'x': '0', 'y': 't', 'z': '0'}, 'scale': [3, 1, 1]}
        self.assertFalse(check.check_boats({'objects': objs, 'assemblies': [flat]}, 'boat')[0])
        tilt = {'id': 'home', 'rotation': {'x': '0.1*sin(t)', 'y': '0', 'z': '0'}, 'scale': [1, 1, 1]}
        self.assertIsNone(check.check_boats({'objects': objs, 'assemblies': [tilt]}, 'boat')[0])


class MainExitTests(unittest.TestCase):
    def run_main(self, results):
        saved = {k: getattr(check, k) for k in ('check_fog', 'check_sea', 'check_horizon', 'check_beam', 'check_boats')}
        values = iter(results)
        try:
            for k in saved:
                setattr(check, k, lambda *a, _v=next(values): _v)
            with tempfile.TemporaryDirectory() as tmp:
                png = Path(tmp) / 'f.png'
                Image.fromarray(np.zeros((40, 40, 3), np.uint8)).save(png)
                plan = Path(tmp) / 'plan.json'
                plan.write_text(json.dumps({'scene': {'environment': {}, 'objects': []}}))
                return check.main([str(plan), str(png), str(png), '--label-px', '0'])
        finally:
            for k, v in saved.items():
                setattr(check, k, v)

    def test_exit_codes(self):
        ok, bad, unk = (True, ''), (False, ''), (None, '')
        self.assertEqual(self.run_main([ok] * 5), 0)
        self.assertEqual(self.run_main([ok, ok, unk, ok, ok]), 3)
        self.assertEqual(self.run_main([ok, bad, unk, ok, ok]), 1)


class FrameTests(unittest.TestCase):
    def test_grid_tiles_drop_label_strip(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / 'grid.png'
            Image.fromarray(np.zeros((200, 300, 3), np.uint8)).save(path)
            frames = check.load_frames([path], (3, 2), 30)
        self.assertEqual(len(frames), 6)
        self.assertEqual(frames[0].shape, (70, 100, 3))


class ExportSelectionTests(unittest.TestCase):
    def project(self, tmp, schema_version=2, html=True):
        root = Path(tmp) / 'projects' / 'p1'
        (root / 'artifacts').mkdir(parents=True)
        (root / 'plans').mkdir()
        (root / 'previews').mkdir()
        (root / 'plans' / 'plan2.json').write_text(json.dumps({'scene': {'schema_version': schema_version}}))
        if html:
            (root / 'artifacts' / 'plan2.html').write_text('<html></html>')
        return {'tool': 'rekindra_preview', 'project_id': 'p1', 'plan_id': 'plan2',
                'path': str(root / 'previews' / 'sheet.png')}

    def test_preview_of_revised_world_is_selected(self):
        with tempfile.TemporaryDirectory() as tmp:
            item = self.project(tmp)
            self.assertTrue(export.world_html(item).endswith('plan2.html'))

    def test_unbuilt_or_non_world_preview_is_skipped(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertIsNone(export.world_html(self.project(tmp, html=False)))
        with tempfile.TemporaryDirectory() as tmp:
            self.assertIsNone(export.world_html(self.project(tmp, schema_version=1)))

    def test_corrupt_or_non_object_plan_is_skipped(self):
        for text in ('{"scene": ', '[]', '{"scene": null}'):
            with tempfile.TemporaryDirectory() as tmp:
                item = self.project(tmp)
                (Path(tmp) / 'projects' / 'p1' / 'plans' / 'plan2.json').write_text(text)
                self.assertIsNone(export.world_html(item), text)

    def test_plan_path_from_summary_is_preferred(self):
        with tempfile.TemporaryDirectory() as tmp:
            item = self.project(tmp, schema_version=1)  # the default plans/ copy is not a world
            other = Path(tmp) / 'elsewhere.json'
            other.write_text(json.dumps({'scene': {'schema_version': 2}}))
            self.assertTrue(export.world_html(dict(item, plan_path=str(other))).endswith('plan2.html'))

    def test_missing_plan_path_does_not_fall_back(self):
        with tempfile.TemporaryDirectory() as tmp:
            item = dict(self.project(tmp), plan_path=str(Path(tmp) / 'gone.json'))
            self.assertIsNone(export.world_html(item))

    def test_create_world_path_is_used_directly(self):
        self.assertEqual(export.world_html({'tool': 'rekindra_create_world', 'path': 'x.html'}), 'x.html')


if __name__ == '__main__':
    unittest.main()
