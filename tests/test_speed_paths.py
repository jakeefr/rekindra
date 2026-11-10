"""The faster paths do the same work with fewer calls: nothing they accept or reject changes."""
import importlib
import json
import unittest
from pathlib import Path
from unittest import mock

import test_recover_evidence as recover_tests
from test_worlds import world

plugin = recover_tests.plugin


def packaged(name):
    return importlib.import_module(plugin.__name__ + '.rekindra_core.' + name)


class SpeedPathTests(unittest.TestCase):
    def setUp(self):
        recover_tests.RecoverEvidenceTests.setUp(self)
        self.store = packaged('projects').ProjectStore(self.store.root)
        self.pid = self.project['project_id']

    tearDown = recover_tests.RecoverEvidenceTests.tearDown
    recover = recover_tests.RecoverEvidenceTests.recover

    def call(self, tool, args):
        raw = self.handlers[tool](args)
        return raw, json.loads(raw)

    # --- one call recovers the whole folder ------------------------------------------------

    def test_whole_folder_recover_lists_every_asset_once(self):
        raw, out = self.call('rekindra_recover', {'project_id': self.pid})
        self.assertTrue(out['ok'], out)
        result = out['result']
        self.assertTrue(result['untrusted_content'])
        self.assertEqual(result['asset_count'], len(self.ids))
        seen = [r['asset_id'] for r in result['recovered']] + [r['asset_id'] for r in result['not_recovered']]
        self.assertEqual(sorted(seen), sorted(self.ids.values()))
        by_id = {r['asset_id']: r for r in result['recovered']}
        image = by_id[self.ids['photo.tga']]
        self.assertEqual((image['kind'], image['source_path']), ('image', 'photo.tga'))
        self.assertTrue(Path(image['path']).is_file())
        self.assertEqual((image['width'], image['height']) > (0, 0), True)
        note = by_id[self.ids['notes.txt']]
        self.assertEqual((note['kind'], note['source_path']), ('evidence', 'notes.txt'))
        self.assertTrue(note['evidence'])
        self.assertNotIn('not_attempted', result)
        self.assertLessEqual(len(raw), plugin.handlers.SUMMARY_MAX_CHARS)

    def test_whole_folder_recover_matches_the_single_calls(self):
        whole = self.call('rekindra_recover', {'project_id': self.pid})[1]['result']
        by_id = {r['asset_id']: r for r in whole['recovered']}
        for name in ('notes.txt', 'photo.tga'):
            single = self.recover(name)
            self.assertTrue(single['ok'], single)
            for key in ('format', 'width', 'height', 'intake_status', 'dossier_status', 'evidence'):
                if key in single['result'] and key in by_id[self.ids[name]]:
                    self.assertEqual(by_id[self.ids[name]][key], single['result'][key], (name, key))

    def test_one_failing_asset_is_listed_and_the_rest_still_recover(self):
        real = self.store.recover
        project_error = packaged('projects').ProjectError

        def flaky(project_id, asset_id, *rest, **kw):
            if asset_id == self.ids['photo.tga']:
                raise project_error('Image could not be decoded: truncated pixel data')
            return real(project_id, asset_id, *rest, **kw)
        with mock.patch.object(self.store, 'recover', side_effect=flaky):
            out = self.call('rekindra_recover', {'project_id': self.pid})[1]
        self.assertTrue(out['ok'], out)
        failed = out['result']['not_recovered']
        self.assertEqual([(f['asset_id'], f['source_path'], f['code']) for f in failed],
                         [(self.ids['photo.tga'], 'photo.tga', 'invalid_input')])
        self.assertIn('truncated pixel data', failed[0]['message'])
        self.assertIn(self.ids['notes.txt'], [r['asset_id'] for r in out['result']['recovered']])

    def test_many_assets_stay_one_reply_under_the_host_budget(self):
        assets = [{'asset_id': f'{i:032x}', 'source_path': f'scan-{i:03d}-' + 'n' * 60 + '.tga'} for i in range(55)]
        image = {'format': 'tga', 'width': 640, 'height': 480, 'path': 'D:/' + 'p' * 150 + '.png',
                 'palette': [{'hex': '#102030', 'share': .2}] * 8, 'warnings': ['w' * 120]}
        store = mock.Mock()
        store.status.return_value = {'assets': assets}
        store.recover.side_effect = lambda project_id, asset_id, reader: dict(image)
        reply = plugin.handlers.recover_all(store, self.pid, None)
        self.assertEqual(store.recover.call_count, plugin.handlers.RECOVER_ALL_ASSETS)
        self.assertLessEqual(len(json.dumps({'ok': True, 'result': reply}, ensure_ascii=False)), plugin.handlers.SUMMARY_MAX_CHARS)
        listed = len(reply['recovered'])
        self.assertEqual(listed + reply.get('recovered_not_listed', {}).get('count', 0), plugin.handlers.RECOVER_ALL_ASSETS)
        self.assertGreater(listed, 20)
        self.assertEqual([r['asset_id'] for r in reply['recovered']], [a['asset_id'] for a in assets[:listed]])
        # A smaller folder keeps the head's details and shortens only the tail.
        store.status.return_value = {'assets': assets[:20]}
        small = plugin.handlers.recover_all(store, self.pid, None)
        self.assertLessEqual(len(json.dumps({'ok': True, 'result': small}, ensure_ascii=False)), plugin.handlers.SUMMARY_MAX_CHARS)
        self.assertEqual(len(small['recovered']), 20)
        self.assertIn('width', small['recovered'][0])
        self.assertNotIn('width', small['recovered'][-1])
        self.assertEqual(reply['not_attempted']['count'], 15)
        self.assertIn('asset_id', reply['not_attempted']['next_step'])
        self.assertIn('rekindra_recover', reply['recovered_note'])

    def test_recover_schema_makes_asset_id_optional_and_says_so(self):
        schema = plugin.schemas.SCHEMAS['rekindra_recover']
        self.assertEqual(schema['parameters']['required'], ['project_id'])
        self.assertIn('ONE call', schema['description'])
        self.assertIn('rekindra_', schema['parameters']['properties']['asset_id']['description'])

    # --- preview in the same call ----------------------------------------------------------

    def world_args(self, **extra):
        return {'project_id': self.pid, 'asset_ids': [self.ids['photo.tga']], 'scene': world(self.ids['photo.tga']), **extra}

    def test_preview_flag_must_be_a_boolean(self):
        for tool, args in (('rekindra_create_world', self.world_args(preview='yes')),
                           ('rekindra_revise_world', {'project_id': self.pid, 'plan_id': 'a' * 32, 'edits': [], 'preview': 1})):
            out = self.call(tool, args)[1]
            self.assertFalse(out['ok'], out)
            self.assertIn('preview must be true or false', out['error']['message'])
            self.assertIn(tool, out['error']['message'])

    def test_preview_flag_is_documented_on_both_tools(self):
        for tool in ('rekindra_create_world', 'rekindra_revise_world'):
            schema = plugin.schemas.SCHEMAS[tool]
            self.assertEqual(schema['parameters']['properties']['preview']['type'], 'boolean')
            self.assertNotIn('preview', schema['parameters']['required'])
            self.assertIn('preview: true', schema['description'])

    def test_create_world_embeds_the_same_preview_result(self):
        sheet = {'path': 'sheet.png', 'export_gate': {'blocked': False}, 'next_step': 'export'}
        with mock.patch.object(packaged('preview'), 'preview_scene', return_value=sheet) as render:
            plain = self.call('rekindra_create_world', self.world_args())[1]
            self.assertTrue(plain['ok'], plain)
            self.assertNotIn('preview', plain['result'])
            self.assertEqual(render.call_count, 0)
            out = self.call('rekindra_create_world', self.world_args(preview=True))[1]
        self.assertTrue(out['ok'], out)
        self.assertEqual(out['result']['preview'], sheet)
        args, kwargs = render.call_args
        self.assertEqual((args[1], args[2], kwargs), (self.pid, out['result']['plan_id'], {'draft': True}))
        self.assertEqual(set(out['result']) - {'preview'}, set(plain['result']))
        self.assertEqual(out['result']['warnings'], plain['result']['warnings'])

    def test_failed_render_keeps_the_saved_plan(self):
        project_error = packaged('projects').ProjectError
        with mock.patch.object(packaged('preview'), 'preview_scene', side_effect=project_error('No supported browser was found')):
            out = self.call('rekindra_create_world', self.world_args(preview=True))[1]
        self.assertTrue(out['ok'], out)
        self.assertRegex(out['result']['plan_id'], '^[0-9a-f]{32}$')
        self.assertNotIn('preview', out['result'])
        self.assertIn('No supported browser', out['result']['preview_error']['message'])
        self.assertIn('rekindra_preview', out['result']['preview_error']['next_step'])
        status = self.call('rekindra_preview', {'project_id': self.pid, 'plan_id': 'not-an-id'})[1]
        self.assertFalse(status['ok'])

    def test_revise_world_embeds_the_preview_of_the_new_plan(self):
        created = self.call('rekindra_create_world', self.world_args())[1]['result']
        edits = [{'object_id': 'sea', 'field': 'roughness', 'value': .5}]
        sheet = {'path': 'sheet.png'}
        with mock.patch.object(packaged('preview'), 'preview_scene', return_value=sheet) as render:
            out = self.call('rekindra_revise_world', {'project_id': self.pid, 'plan_id': created['plan_id'],
                                                      'edits': edits, 'preview': True})[1]
        self.assertTrue(out['ok'], out)
        self.assertEqual(out['result']['preview'], sheet)
        self.assertNotEqual(out['result']['plan_id'], created['plan_id'])
        self.assertEqual(render.call_args[0][2], out['result']['plan_id'])

    # --- the verified recovered PNG is reused ----------------------------------------------

    def test_sources_reuse_the_verified_recovered_image(self):
        compositions = packaged('compositions').CompositionStore(self.store)
        aid = self.ids['photo.tga']
        with mock.patch.object(self.store, 'recover', wraps=self.store.recover) as decode:
            first = compositions.sources(self.pid, [aid])
            self.assertEqual(decode.call_count, 1)
            again = compositions.sources(self.pid, [aid])
            self.assertEqual(decode.call_count, 1)
        self.assertEqual(first, again)
        artifact = next(a for a in self.store.status(self.pid)['artifacts']
                        if a.get('asset_id') == aid and a.get('kind') == 'recovered')
        Path(artifact['path']).write_bytes(b'not the recovered image')
        with mock.patch.object(self.store, 'recover', wraps=self.store.recover) as decode:
            repaired = compositions.sources(self.pid, [aid])
            self.assertEqual(decode.call_count, 1)
        self.assertEqual(first, repaired)
        Path(artifact['path']).unlink()
        with mock.patch.object(self.store, 'recover', wraps=self.store.recover) as decode:
            self.assertEqual(compositions.sources(self.pid, [aid]), first)
            self.assertEqual(decode.call_count, 1)

    def test_changed_source_is_not_served_from_the_saved_image(self):
        compositions = packaged('compositions').CompositionStore(self.store)
        aid = self.ids['photo.tga']
        compositions.sources(self.pid, [aid])
        project = self.store.status(self.pid)
        asset = dict(next(a for a in project['assets'] if a['asset_id'] == aid), sha256='0' * 64)
        self.assertIsNone(compositions._saved_tga(project, asset))

    def test_stripe_refusal_is_repeated_not_cached_away(self):
        worlds = packaged('worlds')
        scene_error = packaged('scenes').SceneError
        worlds._refuse_stripes.cache_clear()
        worlds._refuse_stripes('sin(u*6.28)*0.1')
        worlds._refuse_stripes('sin(u*6.28)*0.1')
        self.assertEqual(worlds._refuse_stripes.cache_info().hits, 1)
        refused = next((e for e in ('step(0.5,fract(u*40.))', 'floor(u*40.)', 'step(.5,fract(v*30.))*sin(u*90.)')
                        if self._refuses(worlds, scene_error, e)), None)
        if refused is not None:
            for _ in range(2):
                with self.assertRaises(scene_error):
                    worlds._refuse_stripes(refused)

    @staticmethod
    def _refuses(worlds, scene_error, expression):
        try:
            worlds._refuse_stripes(expression)
        except scene_error:
            return True
        return False


if __name__ == '__main__':
    unittest.main()
