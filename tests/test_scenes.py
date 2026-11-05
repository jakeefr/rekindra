import copy
import json
import struct
from pathlib import Path
import unittest

from rekindra_core.scenes import validate_scene, SceneError
from rekindra_core.compositions import CompositionStore, jpeg_dimensions
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
    def test_fragment_tracks_are_bounded_and_ordered(self):
        s=scene();layer=s['layers'][0];layer['kind']='fragments'
        key={'at':0,'x':.5,'y':.5,'scale':1,'rotation':0,'opacity':1,'spread':0,'turn':0}
        layer['track']=[key,{**key,'at':4,'spread':1,'turn':90}]
        validated=validate_scene(s,{'a'*32})
        self.assertEqual(validated['layers'][0]['columns'],24)
        for keys in ([key,key], [key,{**key,'at':5}], [key,{**key,'at':4,'scale':99}]):
            bad=copy.deepcopy(s);bad['layers'][0]['track']=keys
            with self.assertRaises(SceneError):validate_scene(bad,{'a'*32})
        bad=copy.deepcopy(s);bad['layers'][0]['columns']=10000
        with self.assertRaises(SceneError):validate_scene(bad,{'a'*32})

    def test_jpeg_header_bounds(self):
        for marker in (0xc0, 0xc2):
            data = b'\xff\xd8\xff'+bytes([marker])+struct.pack('>HBHHB',11,8,360,640,1)+b'\x01\x11\x00'
            self.assertEqual(jpeg_dimensions(data), (640,360))
            for cut in (2, 5, 10, len(data)-1):
                with self.assertRaises(SceneError): jpeg_dimensions(data[:cut])
        with self.assertRaises(SceneError): jpeg_dimensions(b'\xff\xd8\xff\xe0\x00\x01')

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
    def test_maximum_track_plan_can_be_built(self):
        (self.source / 'old.tga').write_bytes(fixture())
        p=self.store.inspect(self.source);aid=p['assets'][0]['asset_id'];s=scene(aid)
        layer=s['layers'][0]
        layer['track']=[{'at':i*4/15,'x':.1234567891234567,'y':.2345678912345678,
                         'scale':1.345678912345678,'rotation':23.45678912345678,'opacity':.9876543219876543,
                         'spread':.4567891234567891,'turn':12.34567891234567} for i in range(16)]
        s['layers']=[{**copy.deepcopy(layer),'id':f'layer{i}'} for i in range(24)]
        c=CompositionStore(self.store);plan=c.save_plan(p['project_id'],s,[aid],{})
        self.assertTrue(Path(c.build(p['project_id'],plan['plan_id'])['path']).is_file())

    def test_jpeg_dimensions_rejected_before_model_submission(self):
        data = b'\xff\xd8\xff\xc0' + struct.pack('>HBHHB', 11, 8, 65535, 65535, 1) + b'\x01\x11\x00' + b'\xff\xd9'
        (self.source / 'huge.jpg').write_bytes(data)
        p = self.store.inspect(self.source)
        with self.assertRaisesRegex(SceneError, 'pixel budget'):
            CompositionStore(self.store).sources(p['project_id'], [p['assets'][0]['asset_id']])

    def test_agent_authored_scene_builds_without_auxiliary_model(self):
        from test_plugin import plugin
        (self.source / 'old.tga').write_bytes(fixture())
        p = self.store.inspect(self.source); aid = p['assets'][0]['asset_id']
        result = json.loads(plugin.handlers.make_handlers(lambda: self.store)['rekindra_compose'](
            {'project_id': p['project_id'], 'asset_ids': [aid], 'scene': scene(aid), 'allow_text': True}))
        self.assertTrue(result['ok'], result)
        self.assertTrue(Path(result['result']['path']).is_file())

    def test_compose_rejects_unsolicited_text(self):
        from test_plugin import plugin
        (self.source / 'old.tga').write_bytes(fixture())
        p = self.store.inspect(self.source); aid = p['assets'][0]['asset_id']
        result = json.loads(plugin.handlers.make_handlers(lambda: self.store)['rekindra_compose'](
            {'project_id': p['project_id'], 'asset_ids': [aid], 'scene': scene(aid)}))
        self.assertFalse(result['ok'])
        self.assertIn('text', result['error']['message'])

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


