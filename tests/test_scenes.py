import copy
import json
from pathlib import Path
import unittest

from rekindra_core.scenes import validate_scene, SceneError
from rekindra_core.compositions import CompositionStore
import test_projects
from test_tga import fixture


def scene(asset_id='a'*32):
    return {'schema_version': 1, 'title': 'Green afterglow', 'mood': 'dreamy',
            'reason': 'The original image gives the scene its color and central shape.',
            'duration': 4, 'width': 1280, 'height': 720, 'background': '#10272a',
            'palette': ['#abc779', '#e8eddd'], 'seed': 17,
            'layers': [{'id': 'photo', 'kind': 'image', 'asset_id': asset_id, 'start': 0, 'end': 4,
                        'x': .5, 'y': .5, 'width': .55, 'height': .65, 'motion': 'drift'},
                       {'id': 'title', 'kind': 'text', 'text': 'A little light remains', 'start': 0, 'end': 4,
                        'x': .5, 'y': .9, 'font_size': 40, 'color': '#e8eddd'}]}


class SceneTests(unittest.TestCase):
    def test_normalizes_valid_scene_without_mutating_input(self):
        raw = scene()
        result = validate_scene(raw, {'a'*32})
        self.assertEqual(result['layers'][0]['opacity'], 1)
        self.assertNotIn('opacity', raw['layers'][0])

    def test_rejects_invalid_or_unbounded_documents(self):
        changes = [('duration', float('nan')), ('duration', 31), ('seed', True),
                   ('width', 99999), ('palette', ['red']), ('background', 'url(https://evil)')]
        for key, value in changes:
            candidate = scene(); candidate[key] = value
            with self.subTest(key=key):
                with self.assertRaises(SceneError): validate_scene(candidate, {'a'*32})
        for change in ({'x': float('inf')}, {'asset_id': '../secret'}, {'kind': 'script'},
                       {'url': 'https://evil'}, {'end': 0}, {'count': 1_000_000}):
            candidate = scene(); candidate['layers'][0].update(change)
            with self.subTest(change=change):
                with self.assertRaises(SceneError): validate_scene(candidate, {'a'*32})
        candidate = scene(); candidate['layers'] *= 13
        with self.assertRaises(SceneError): validate_scene(candidate, {'a'*32})


class CompositionTests(unittest.TestCase):
    setUp = test_projects.ProjectTests.setUp
    def test_plan_build_and_safe_embedding(self):
        (self.source / 'old.tga').write_bytes(fixture())
        p = self.store.inspect(self.source)
        aid = p['assets'][0]['asset_id']
        compositions = CompositionStore(self.store)
        sources = compositions.sources(p['project_id'], [aid])
        self.assertEqual(sources[0]['mime_type'], 'image/png')
        raw = scene(aid)
        raw['title'] = '/*PLAYER_RUNTIME*/'
        raw['layers'][1]['text'] = '</script><img src=x onerror=alert(1)>'
        plan = compositions.save_plan(p['project_id'], raw, [aid], {'provider': 'test', 'model': 'fixture'})
        built = compositions.build(p['project_id'], plan['plan_id'])
        html = Path(built['path']).read_text(encoding='utf-8')
        self.assertNotIn('</script><img', html)
        self.assertIn('\\u003c/script', html)
        self.assertIn("connect-src 'none'", html)
        self.assertIn('<title>/*PLAYER_RUNTIME*/', html)
        self.assertEqual(built['kind'], 'generated')
        self.assertEqual(built['source_ids'], [aid])

    def test_corrupted_sources_and_invalid_plans_fail_before_export(self):
        (self.source / 'old.tga').write_bytes(fixture())
        p = self.store.inspect(self.source); aid = p['assets'][0]['asset_id']
        compositions = CompositionStore(self.store)
        plan = compositions.save_plan(p['project_id'], scene(aid), [aid], {})
        (self.store.root / p['project_id'] / 'originals' / aid).write_bytes(b'changed')
        with self.assertRaises(ValueError): compositions.build(p['project_id'], plan['plan_id'])
        with self.assertRaises(ValueError): compositions.build(p['project_id'], '../secret')

    def test_rejects_excessive_source_selection(self):
        p = self.store.inspect(self.source)
        with self.assertRaises(ValueError): CompositionStore(self.store).sources(p['project_id'], ['a'*32]*7)


