"""The preview's warnings bind: a flagged world cannot get a video-capable export unanswered."""
import json
from importlib import import_module
from pathlib import Path
import unittest
from unittest import mock

from test_worlds import world
import test_recover_evidence as recover_tests

plugin = recover_tests.plugin
SCHEMAS = plugin.schemas.SCHEMAS
ROOT = Path(__file__).resolve().parents[1]
gate = import_module(f'{plugin.__name__}.rekindra_core.export_gate')
compositions_module = import_module(f'{plugin.__name__}.rekindra_core.compositions')
preview_module = import_module(f'{plugin.__name__}.rekindra_core.preview')

WARM = 'water rendered #6B4F4A vs intended #28465F: lighting is shifting it warm'


def region(name, over, flag=WARM):
    return {'region': name, 'intended': '#28465F', 'rendered': '#6B4F4A', 'rendered_coverage': 80.0,
            'delta_e': 40.0 if over else 5.0, 'threshold': 20, 'over_threshold': over,
            'objects': ['sea'], 'flag': flag}


DRIFT = {'status': 'drift', 'reference': 'source-palette',
         'regions': [region('top band', False, ''), region('bottom band', True)]}
CLEAN = {'status': 'ok', 'reference': 'source-palette', 'regions': [region('bottom band', False, '')]}
BOTTOM = 'palette:bottom-band'
REASON = 'water deliberately shifted warm per the notes'


def hills(aid):
    """A world whose wide backdrop shows its end to the camera."""
    scene = world(aid)
    scene['environment']['fog_density'] = .002
    pose = {'eye': [15, 10, 24], 'target': [.4, 3, 0], 'fov': 44}
    scene['camera'] = [dict(pose, at=0), dict(pose, at=scene['duration'])]
    scene['objects'].append(dict(scene['objects'][0], id='hills',
                                 position={'x': '(u-0.5)*180', 'y': 'v*20', 'z': '-32'}))
    return scene


class ExportGateTests(recover_tests.RecoverEvidenceTests):
    def call(self, tool, **args):
        return json.loads(self.handlers[tool]({'project_id': self.project['project_id'], **args}))

    def compositions(self):
        return compositions_module.CompositionStore(self.store)

    def plan(self, plan_id):
        return self.compositions().load_plan(self.project['project_id'], plan_id)

    def create(self, scene=None):
        aid = self.ids['photo.tga']
        out = self.call('rekindra_create_world', asset_ids=[aid], scene=scene or world(aid))
        self.assertTrue(out['ok'], out)
        return out['result']['plan_id']

    def revise(self, plan_id, title='Next attempt'):
        out = self.call('rekindra_revise_world', plan_id=plan_id, edits=[{'field': 'title', 'value': title}])
        self.assertTrue(out['ok'], out)
        return out['result']['plan_id']

    def preview(self, plan_id, drift=DRIFT, review_camera=None):
        return gate.preview_gate(self.store, self.project['project_id'], self.plan(plan_id), drift, review_camera)

    def export(self, plan_id, acknowledgments=None):
        args = {'plan_id': plan_id}
        if acknowledgments is not None:
            args['acknowledgments'] = acknowledgments
        return self.call('rekindra_export', **args)

    def assertBlocked(self, out):
        self.assertFalse(out['ok'], out)
        self.assertEqual(out['error']['code'], 'export_blocked')
        return out['error']['message']

    def flagged_revisions(self, count, drift=DRIFT):
        current = self.create()
        self.preview(current, drift)
        for step in range(count):
            current = self.revise(current, f'Attempt {step}')
            self.preview(current, drift)
        return current

    def test_export_needs_a_preview_of_this_exact_plan(self):
        plan_id = self.create()
        self.assertIn('rekindra_preview', self.assertBlocked(self.export(plan_id)))
        self.preview(plan_id, CLEAN)
        self.assertBlocked(self.export(self.revise(plan_id)))

    def test_an_inspection_view_does_not_count_as_the_preview(self):
        plan_id = self.create()
        self.assertIsNone(self.preview(plan_id, CLEAN, {'eye': [1, 1, 1], 'target': [0, 0, 0], 'fov': 40}))
        self.assertBlocked(self.export(plan_id))

    def test_drift_blocks_and_the_message_names_the_issue_and_fixes(self):
        plan_id = self.create()
        shown = self.preview(plan_id)
        self.assertEqual([w['warning_id'] for w in shown['warnings']], [BOTTOM])
        out = self.export(plan_id)
        message = self.assertBlocked(out)
        for part in (BOTTOM, WARM, 'rekindra_revise_world', 'rekindra_preview', 'acknowledgments', '0 of 3'):
            self.assertIn(part, message)
        self.assertEqual([w['warning_id'] for w in out['error']['warnings']], [BOTTOM])

    def test_backdrop_edge_blocks_even_with_clean_colors(self):
        plan_id = self.create(hills(self.ids['photo.tga']))
        shown = self.preview(plan_id, CLEAN)
        self.assertIn('backdrop:hills', [w['warning_id'] for w in shown['warnings']])
        message = self.assertBlocked(self.export(plan_id))
        for part in ('backdrop:hills', 'end is in frame', 'move it closer'):
            self.assertIn(part, message)

    def test_override_with_a_reason_is_accepted_and_recorded(self):
        plan_id = self.create()
        self.preview(plan_id)
        out = self.export(plan_id, [{'warning_id': BOTTOM, 'reason': '  ' + REASON + ' '}])
        self.assertTrue(out['ok'], out)
        result = out['result']
        self.assertEqual((result['status'], result['format']), ('acknowledged', 'html'))
        self.assertEqual(result['acknowledgments'], [{'warning_id': BOTTOM, 'reason': REASON}])
        stored = json.loads(Path(result['provenance_path']).read_text(encoding='utf-8'))
        self.assertEqual(stored['acknowledgments'], [{'warning_id': BOTTOM, 'reason': REASON}])
        self.assertEqual(stored['warnings'][0]['message'], WARM)
        self.assertEqual(stored['html_sha256'], result['sha256'])
        document = Path(result['path']).read_text(encoding='utf-8')
        self.assertIn(REASON, document)
        self.assertNotIn('"export_locked"', document)
        self.assertIn('"export_provenance"', document)

    def test_bad_overrides_are_refused(self):
        plan_id = self.create(hills(self.ids['photo.tga']))
        drift_ids = [w['warning_id'] for w in self.preview(plan_id)['warnings']]
        self.assertGreaterEqual(len(drift_ids), 2)
        good = [{'warning_id': i, 'reason': REASON} for i in drift_ids]
        cases = {'partial': good[:-1],
                 'blank': [dict(good[0], reason='          ')] + good[1:],
                 'short': [dict(good[0], reason='because')] + good[1:],
                 'long': [dict(good[0], reason='x' * 201)] + good[1:],
                 'unknown': good + [{'warning_id': 'palette:elsewhere', 'reason': REASON}],
                 'duplicate': good + [good[0]],
                 'missing reason': [{'warning_id': good[0]['warning_id']}] + good[1:],
                 'extra key': [dict(good[0], approved=True)] + good[1:],
                 'not a list': 'yes'}
        for name, acks in cases.items():
            with self.subTest(name):
                self.assertBlocked(self.export(plan_id, acks))
        self.assertTrue(self.export(plan_id, good)['ok'])

    def test_cap_allows_export_after_three_flagged_cycles_with_warnings_recorded(self):
        two = self.flagged_revisions(2)
        self.assertIn('2 of 3', self.assertBlocked(self.export(two)))
        three = self.revise(two, 'Third')
        self.preview(three)
        out = self.export(three)
        self.assertTrue(out['ok'], out)
        result = out['result']
        self.assertEqual((result['status'], result['revise_preview_cycles']), ('cycle_cap', 3))
        self.assertEqual([w['warning_id'] for w in result['warnings']], [BOTTOM])
        stored = json.loads(Path(result['provenance_path']).read_text(encoding='utf-8'))
        self.assertEqual((stored['status'], stored['warnings'][0]['message']), ('cycle_cap', WARM))

    def test_previewing_one_plan_again_does_not_earn_cycles(self):
        one = self.flagged_revisions(1)
        for _ in range(4):
            shown = self.preview(one)
        self.assertEqual(shown['revise_preview_cycles'], 1)
        self.assertBlocked(self.export(one))

    def test_a_revision_never_previewed_does_not_count(self):
        current = self.create()
        self.preview(current)
        for step in range(3):
            current = self.revise(current, f'Blind {step}')
        self.preview(current)
        self.assertIn('1 of 3', self.assertBlocked(self.export(current)))

    def test_clean_results_export_without_any_acknowledgment(self):
        for drift in (CLEAN, {'status': 'not_measured', 'reason': 'no reference'},
                      {'status': 'unavailable', 'reason': 'no pillow'}):
            with self.subTest(drift['status']):
                plan_id = self.create()
                self.preview(plan_id, drift)
                out = self.export(plan_id)
                self.assertTrue(out['ok'], out)
                self.assertEqual((out['result']['status'], out['result']['warnings']), ('clear', []))

    def test_a_fixed_revision_clears_the_gate(self):
        flagged = self.create()
        self.preview(flagged)
        fixed = self.revise(flagged)
        self.preview(fixed, CLEAN)
        self.assertEqual(self.export(fixed)['result']['status'], 'clear')
        self.assertBlocked(self.export(flagged))

    def test_a_corrupt_preview_record_fails_closed(self):
        plan_id = self.create()
        self.preview(plan_id, CLEAN)
        path = self.store._project(self.project['project_id']) / 'artifacts' / f'{plan_id}-preview-record.json'
        for text in ('{"plan_id": ', '[]', json.dumps({'plan_id': 'other', 'palette_drift': CLEAN}),
                     json.dumps({'plan_id': plan_id, 'palette_drift': {'status': 'ok-ish'}}),
                     json.dumps({'plan_id': plan_id, 'palette_drift': {'status': 'drift', 'regions': [{}]}})):
            with self.subTest(text):
                path.write_text(text, encoding='utf-8')
                self.assertBlocked(self.export(plan_id))

    def test_compositions_are_not_exported_here(self):
        aid = self.ids['photo.tga']
        from test_scenes import scene  # local: only this test needs the composition fixture
        out = self.call('rekindra_compose', asset_ids=[aid], scene=scene(aid), allow_text=True)
        self.assertTrue(out['ok'], out)
        refused = self.export(out['result']['plan_id'])
        self.assertFalse(refused['ok'])
        self.assertEqual(refused['error']['code'], 'invalid_input')
        self.assertIn('world', refused['error']['message'])

    def test_tool_built_worlds_are_locked_drafts(self):
        pid = self.project['project_id']
        plan_id = self.create()
        locked = '"export_locked": true'
        artifact = Path(self.store._project(pid)) / 'artifacts' / f'{plan_id}.html'
        self.assertIn(locked, artifact.read_text(encoding='utf-8'))
        out = self.call('rekindra_build', plan_id=plan_id)
        self.assertIn(locked, Path(out['result']['path']).read_text(encoding='utf-8'))
        # A direct library build keeps fixtures and scripts working.
        plain = self.compositions().build(pid, plan_id)
        self.assertNotIn(locked, Path(plain['path']).read_text(encoding='utf-8'))

    def test_the_preview_tool_rebuilds_the_html_as_a_draft(self):
        seen = {}

        def fake(store, project_id, plan_id, review_camera=None, draft=False):
            seen.update(plan_id=plan_id, draft=draft)
            return {'kind': 'rendered-frame-review'}
        with mock.patch.object(preview_module, 'preview_scene', fake):
            self.assertTrue(self.call('rekindra_preview', plan_id='p' * 32)['ok'])
        self.assertEqual(seen, {'plan_id': 'p' * 32, 'draft': True})

    def test_player_refuses_a_locked_draft_through_ui_and_api(self):
        player = (ROOT / 'runtime' / 'player.js').read_text(encoding='utf-8')
        self.assertIn("if(data.export_locked)throw Error(", player)
        self.assertIn("if(data.export_locked){", player)

    def test_tool_is_registered_and_described(self):
        self.assertIn('rekindra_export', self.handlers)
        self.assertIn('rekindra_export', (ROOT / 'plugin.yaml').read_text(encoding='utf-8'))
        schema = SCHEMAS['rekindra_export']
        self.assertEqual(schema['parameters']['required'], ['project_id', 'plan_id'])
        item = schema['parameters']['properties']['acknowledgments']['items']
        self.assertEqual(sorted(item['required']), ['reason', 'warning_id'])
        for part in ('acknowledgments', 'reason', '3'):
            self.assertIn(part, schema['description'])
        for tool in ('rekindra_preview', 'rekindra_create_world', 'rekindra_revise_world'):
            self.assertIn('rekindra_export', SCHEMAS[tool]['description'], tool)


# Only the tests defined above run for the subclass; inherited recovery tests already run once.
for _name in [n for n in dir(recover_tests.RecoverEvidenceTests) if n.startswith('test_')]:
    if _name not in ExportGateTests.__dict__:
        setattr(ExportGateTests, _name, None)


if __name__ == '__main__':
    unittest.main()
