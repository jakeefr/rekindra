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
        self.assertFalse(ok)
        self.assertIn('unmeasured', detail)


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

    def test_pointed_loft_passes_and_disc_fails(self):
        pts = [[0, -1.4], [.32, -.7], [.45, .2], [.36, 1.0], [-.36, 1.0], [-.45, .2], [-.32, -.7]]
        hull = {'id': 'boat', 'assembly': 'home', 'loft': [{'height': 0, 'points': pts}],
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
        hull = {'id': 'boat', 'assembly': 'home', 'loft': [{'height': 0, 'points': pts}],
                'position': {'x': 'loft_x', 'y': 'loft_y', 'z': 'loft_z'},
                'instances': [{'offset': [0, 0, 0], 'scale': [1, 1, 1]}, {'offset': [3, 0, 0], 'scale': [2.5, 1, 1]}]}
        ok, detail = check.check_boats({'objects': [hull, {'id': 'mast', 'assembly': 'home'}]}, 'boat')
        self.assertFalse(ok, detail)  # the second copy is stretched almost square


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

    def test_create_world_path_is_used_directly(self):
        self.assertEqual(export.world_html({'tool': 'rekindra_create_world', 'path': 'x.html'}), 'x.html')


if __name__ == '__main__':
    unittest.main()
