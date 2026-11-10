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
        failed = [f for f in out['result']['not_recovered'] if f['source_path'] != 'bad.json']
        self.assertEqual([(f['asset_id'], f['source_path'], f['code']) for f in failed],
                         [(self.ids['photo.tga'], 'photo.tga', 'invalid_input')])
        self.assertIn('truncated pixel data', failed[0]['message'])
        self.assertIn(self.ids['notes.txt'], [r['asset_id'] for r in out['result']['recovered']])

    def test_rejected_and_unsupported_sources_are_not_listed_as_recovered(self):
        (self.source / 'blob.txt').write_bytes(bytes(range(256)) * 8)
        inspected = self.call('rekindra_inspect', {'folder': str(self.source)})[1]
        self.assertTrue(inspected['ok'], inspected)
        self.pid = inspected['result']['project_id']
        self.ids = {a['source_path']: a['asset_id'] for a in inspected['result']['assets']}
        out = self.call('rekindra_recover', {'project_id': self.pid})[1]
        self.assertTrue(out['ok'], out)
        result = out['result']
        for row in result['recovered']:
            self.assertNotIn(row.get('intake_status'), ('rejected', 'unsupported'), row)
        missing = {f['source_path']: f for f in result['not_recovered']}
        bad = missing['bad.json']
        self.assertEqual((bad['asset_id'], bad['code'], bad['intake_status']),
                         (self.ids['bad.json'], 'json_non_finite_number', 'rejected'))
        self.assertIn('nothing was recovered', bad['message'])
        self.assertIn('blob.txt', missing)
        self.assertTrue(missing['blob.txt']['code'], missing['blob.txt'])
        self.assertNotIn('bad.json', [r['source_path'] for r in result['recovered']])
        # Every asset is accounted for exactly once.
        listed = [r['asset_id'] for r in result['recovered']] + [f['asset_id'] for f in result['not_recovered']]
        self.assertEqual(sorted(listed), sorted(self.ids.values()))
        self.assertEqual(result['asset_count'], len(self.ids))

    def test_shortened_entries_keep_their_status_and_are_not_called_recovered(self):
        assets = [{'asset_id': f'{i:032x}', 'source_path': f'note-{i:03d}-' + 'n' * 60 + '.txt'} for i in range(30)]
        store = mock.Mock()
        store.status.return_value = {'assets': assets}
        statuses = ('recovered', 'partial', 'recovered_with_warnings')

        def recover(project_id, asset_id, reader):
            return {'dossier': {}, 'asset_id': asset_id}
        store.recover.side_effect = recover
        views = {a['asset_id']: {'asset_id': a['asset_id'], 'kind': 'evidence',
                                 'intake_status': statuses[i % 3], 'dossier_status': 'ready', 'evidence_omitted_from_summary': 0,
                                 'warnings': ['w' * 150] * 4, 'evidence': [{'evidence_id': 'ev-' + 'a' * 24, 'text': 't' * 300}] * 3}
                 for i, a in enumerate(assets)}
        with mock.patch.object(plugin.handlers, 'evidence_summary', side_effect=lambda result: dict(views[result['asset_id']])):
            reply = plugin.handlers.recover_all(store, self.pid, None)
        self.assertLessEqual(len(json.dumps({'ok': True, 'result': reply}, ensure_ascii=False)), plugin.handlers.SUMMARY_MAX_CHARS)
        short = [r for r in reply['recovered'] if 'evidence' not in r]
        self.assertTrue(short, reply)
        for row in short:
            self.assertEqual(row['intake_status'], views[row['asset_id']]['intake_status'])
        note = reply['recovered_note']
        self.assertNotIn('were recovered', note)
        self.assertIn('summarized', note)
        self.assertIn('intake_status', note)

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

    def test_unexpected_failure_on_one_asset_does_not_stop_the_rest(self):
        real = self.store.recover
        for error, code in ((OSError('disk went away'), 'filesystem_error'), (RuntimeError('reader bug'), 'operation_failed')):
            def flaky(project_id, asset_id, *rest, _error=error, **kw):
                if asset_id == self.ids['photo.tga']:
                    raise _error
                return real(project_id, asset_id, *rest, **kw)
            with mock.patch.object(self.store, 'recover', side_effect=flaky):
                out = self.call('rekindra_recover', {'project_id': self.pid})[1]
            self.assertTrue(out['ok'], out)
            failed = [f for f in out['result']['not_recovered'] if f['source_path'] != 'bad.json']
            self.assertEqual([(f['asset_id'], f['code']) for f in failed], [(self.ids['photo.tga'], code)])
            self.assertNotIn(str(error), failed[0]['message'])
            self.assertIn(self.ids['notes.txt'], [r['asset_id'] for r in out['result']['recovered']])

    def _image_store(self, assets, fail=()):
        image = {'format': 'tga', 'width': 640, 'height': 480, 'path': 'D:/' + 'p' * 150 + '.png',
                 'palette': [{'hex': '#102030', 'share': .2}] * 8, 'warnings': ['w' * 120]}
        project_error = packaged('projects').ProjectError
        store = mock.Mock()
        store.status.return_value = {'assets': assets}

        def recover(project_id, asset_id, reader):
            if asset_id in fail:
                raise project_error('Recovery supports common image formats')
            return {'dossier': {}, 'asset_id': asset_id} if asset_id == 'text' else dict(image)
        store.recover.side_effect = recover
        return store

    def test_image_details_are_trimmed_before_the_last_quoted_evidence(self):
        assets = [{'asset_id': f'{i:032x}', 'source_path': f'scan-{i:03d}.tga'} for i in range(30)]
        assets.append({'asset_id': 'text', 'source_path': 'notes.txt'})
        quoted = {'asset_id': 'text', 'kind': 'evidence', 'evidence_omitted_from_summary': 0,
                  'evidence': [{'evidence_id': f'ev-{i}', 'text': 'q' * 200} for i in range(3)]}
        with mock.patch.object(plugin.handlers, 'evidence_summary', return_value=quoted):
            reply = plugin.handlers.recover_all(self._image_store(assets), self.pid, None)
        self.assertLessEqual(len(json.dumps({'ok': True, 'result': reply}, ensure_ascii=False)), plugin.handlers.SUMMARY_MAX_CHARS)
        self.assertEqual(reply['recovered'][-1]['asset_id'], 'text')
        self.assertTrue(reply['recovered'][-1]['evidence'])
        self.assertNotIn('width', reply['recovered'][-2])

    def test_one_call_stops_at_its_time_allowance(self):
        assets = [{'asset_id': f'{i:032x}', 'source_path': f'scan-{i:03d}.tga'} for i in range(6)]
        store = self._image_store(assets)
        with mock.patch.object(plugin.handlers, 'RECOVER_ALL_SECONDS', -1):
            reply = plugin.handlers.recover_all(store, self.pid, None)
        self.assertEqual(store.recover.call_count, 1)
        self.assertEqual(len(reply['recovered']), 1)
        self.assertEqual(reply['not_attempted']['count'], 5)
        self.assertEqual(reply['not_attempted']['asset_ids'], [a['asset_id'] for a in assets[1:]])

    def test_unrecoverable_files_do_not_use_up_the_asset_allowance(self):
        assets = [{'asset_id': f'{i:032x}', 'source_path': f'file-{i:03d}.bin'} for i in range(50)]
        store = self._image_store(assets, fail={a['asset_id'] for a in assets[:45]})
        reply = plugin.handlers.recover_all(store, self.pid, None)
        self.assertEqual(store.recover.call_count, 50)
        self.assertNotIn('not_attempted', reply)
        self.assertEqual([r['asset_id'] for r in reply['recovered']], [a['asset_id'] for a in assets[45:]])
        self.assertEqual(len(reply['not_recovered']) + reply.get('not_recovered_not_listed', {}).get('count', 0), 45)
        self.assertLessEqual(len(json.dumps({'ok': True, 'result': reply}, ensure_ascii=False)), plugin.handlers.SUMMARY_MAX_CHARS)

    def test_many_failures_give_way_before_recovered_details(self):
        assets = [{'asset_id': f'{i:032x}', 'source_path': f'file-{i:03d}.bin'} for i in range(104)]
        assets.append({'asset_id': 'text', 'source_path': 'notes.txt'})
        quoted = {'asset_id': 'text', 'kind': 'evidence', 'evidence_omitted_from_summary': 0,
                  'evidence': [{'evidence_id': f'ev-{i}', 'text': 'q' * 200} for i in range(4)]}
        store = self._image_store(assets, fail={a['asset_id'] for a in assets[:100]})
        real = store.recover.side_effect

        def recover(project_id, asset_id, reader):
            if asset_id == assets[98]['asset_id']:
                raise packaged('projects').ReaderRetry('No reader process could be started in time')
            if asset_id == assets[99]['asset_id']:
                raise RuntimeError('reader bug')
            return real(project_id, asset_id, reader)
        store.recover.side_effect = recover
        with mock.patch.object(plugin.handlers, 'evidence_summary', return_value=quoted):
            reply = plugin.handlers.recover_all(store, self.pid, None)
        self.assertEqual(len(reply['recovered'][-1]['evidence']), 4)
        self.assertEqual([(f['asset_id'], f['code']) for f in reply['not_recovered'][-2:]],
                         [(assets[98]['asset_id'], 'reader_busy'), (assets[99]['asset_id'], 'operation_failed')])
        self.assertEqual(sum(reply['not_recovered_not_listed']['codes'].values()), reply['not_recovered_not_listed']['count'])
        self.assertEqual(set(reply['not_recovered_not_listed']['codes']), {'invalid_input'})
        self.assertLessEqual(len(json.dumps({'ok': True, 'result': reply}, ensure_ascii=False)), plugin.handlers.SUMMARY_MAX_CHARS)
        self.assertEqual(len(reply['recovered']), 5)
        for row in reply['recovered'][:4]:
            self.assertEqual(row['width'], 640)
        self.assertTrue(reply['recovered'][-1]['evidence'])
        self.assertEqual(len(reply['not_recovered']) + reply['not_recovered_not_listed']['count'], 100)
        self.assertTrue(all(f['code'] == 'invalid_input' for f in reply['not_recovered'][:-2]))

    def test_unlisted_retryable_failures_keep_their_asset_ids(self):
        assets = [{'asset_id': f'{i:032x}', 'source_path': 'n' * 100 + f'-{i:03d}.tga'} for i in range(120)]
        store = self._image_store(assets)
        store.recover.side_effect = RuntimeError('reader bug')
        reply = plugin.handlers.recover_all(store, self.pid, None)
        unlisted = reply['not_recovered_not_listed']
        self.assertEqual(len(reply['not_recovered']) + unlisted['count'], 120)
        self.assertEqual(unlisted['codes'], {'operation_failed': unlisted['count']})
        self.assertEqual(len(unlisted['retry_asset_ids']), 12)
        self.assertIn('retry_asset_ids', unlisted['next_step'])

    def test_a_malformed_result_on_one_asset_does_not_fail_the_call(self):
        assets = [{'asset_id': 'text', 'source_path': 'notes.txt'}, {'asset_id': 'a' * 32, 'source_path': 'scan.tga'}]
        store = self._image_store(assets)
        with mock.patch.object(plugin.handlers, 'evidence_summary', side_effect=KeyError('evidence_id')):
            reply = plugin.handlers.recover_all(store, self.pid, None)
        self.assertEqual([r['asset_id'] for r in reply['recovered']], ['a' * 32])
        self.assertEqual([(f['asset_id'], f['code']) for f in reply['not_recovered']], [('text', 'operation_failed')])
        self.assertNotIn('guidance', reply)

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
        compositions = packaged('compositions').CompositionStore(self.store)
        self.assertTrue(compositions.load_plan(self.pid, out['result']['plan_id']))
        stop = packaged('scenes').SceneError('No browser.' + packaged('preview')._STOP)
        with mock.patch.object(packaged('preview'), 'preview_scene', side_effect=stop):
            out = self.call('rekindra_create_world', self.world_args(preview=True))[1]
        self.assertRegex(out['result']['plan_id'], '^[0-9a-f]{32}$')
        self.assertNotIn('rekindra_preview', out['result']['preview_error']['next_step'])
        self.assertNotIn('retry', out['result']['preview_error']['next_step'])
        for error, code in ((OSError('no temp dir'), 'filesystem_error'), (RuntimeError('browser bug'), 'operation_failed')):
            with mock.patch.object(packaged('preview'), 'preview_scene', side_effect=error):
                out = self.call('rekindra_create_world', self.world_args(preview=True))[1]
            self.assertTrue(out['ok'], out)
            self.assertEqual(out['result']['preview_error']['code'], code)
            self.assertNotIn(str(error), out['result']['preview_error']['message'])
            self.assertTrue(compositions.load_plan(self.pid, out['result']['plan_id']))

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
        for _ in range(2):
            with self.assertRaises(scene_error) as caught:
                worlds._refuse_stripes('.35+.25*cos(u*80*pi)')
            self.assertIn('stripes', str(caught.exception))


if __name__ == '__main__':
    unittest.main()
