"""Report checks: object motion with the camera held, haze against misty sources, surfaces the camera flies
into, and defects carried from one preview to the next until a revise answers them."""
import base64
import json
import unittest
from importlib import import_module
from unittest import mock

import test_export_gate as gate_tests
import test_preview_reliability as reliability
from test_worlds import world

plugin = gate_tests.plugin
gate = gate_tests.gate
preview = gate_tests.preview_module
checks = import_module(f'{plugin.__name__}.rekindra_core.report_checks')
SCHEMAS = gate_tests.SCHEMAS

MISTY = [{'hex': '#c4c8cc', 'coverage': 60}, {'hex': '#b8bcc0', 'coverage': 30}, {'hex': '#d0d2d4', 'coverage': 10}]
NIGHT = [{'hex': '#0a0c14', 'coverage': 70}, {'hex': '#f0c040', 'coverage': 20}, {'hex': '#3050a0', 'coverage': 10}]


def still_scene():
    """The test world with no t anywhere: only the camera moves."""
    scene = world()
    scene['objects'][0]['position']['y'] = '.18*sin(u*44)'
    scene['objects'][0]['color_mix'] = '.5'
    return scene


def chip(position, **extra):
    """A small flat surface; position is its centre."""
    x, y, z = position
    return dict({'id': 'chip', 'position': {'x': f'{x}+(u-.5)*.6', 'y': f'{y}+(v-.5)*.6', 'z': f'{z}'},
                 'segments': [4, 4], 'color': '#8a6a22', 'roughness': .5, 'metalness': 0, 'emission': 0}, **extra)


class ObjectMotionTests(unittest.TestCase):
    def test_time_use_is_found_in_any_expression_field(self):
        self.assertTrue(checks.uses_time(world()))
        self.assertFalse(checks.uses_time(still_scene()))
        scene = still_scene()
        scene['objects'][0]['color_mix'] = '.5+.5*sin(t)'
        self.assertTrue(checks.uses_time(scene))

    def test_report_states_plainly_when_only_the_camera_moves(self):
        report = checks.object_motion_report(0.0)
        self.assertFalse(report['objects_move'])
        self.assertEqual(report['statement'], 'objects do not move on their own; only the camera moves')
        self.assertTrue(checks.object_motion_report(3.2)['objects_move'])
        for value in (None, 'x', True, float('nan')):
            self.assertIsNone(checks.object_motion_report(value))

    def test_warning_needs_time_in_the_plan_and_a_still_measurement(self):
        found = checks.object_motion_warnings(world(), 0.02)
        self.assertEqual([w['warning_id'] for w in found], ['frames:objects_still'])
        self.assertIn('only the camera moves', found[0]['message'])
        self.assertEqual(checks.object_motion_warnings(world(), 2.5), [])
        self.assertEqual(checks.object_motion_warnings(still_scene(), 0.0), [])
        self.assertEqual(checks.object_motion_warnings(world(), None), [])

    def test_review_document_keeps_three_values_and_reads_object_motion(self):
        body = json.loads(reliability.document().split('application/json">', 1)[1].split('</script>')[0])
        body['result']['objectMotion'] = 0.004
        page = f'<script id="rekindra-review-result" type="application/json">{json.dumps(body)}</script>'
        self.assertEqual(len(preview._decode_review(page, 6)), 3)
        self.assertEqual(preview._decode_review_full(page, 6)[4], 0.004)
        for bad in (-1, 300, 'still', True, None):
            self.assertIsNone(preview._object_motion({'objectMotion': bad}), bad)


class HazeTests(unittest.TestCase):
    def test_pale_grey_flat_sources_read_misty_and_dark_contrasty_ones_do_not(self):
        self.assertGreaterEqual(checks.source_mist([MISTY]), checks.MISTY_SOURCE)
        self.assertEqual(checks.source_mist([NIGHT]), 0.0)
        self.assertEqual(checks.source_mist([NIGHT, MISTY]), checks.source_mist([MISTY]))
        self.assertIsNone(checks.source_mist([]))
        self.assertIsNone(checks.source_mist([[{'hex': 'nope'}]]))

    def test_scene_haze_grows_with_fog(self):
        thin, thick = world(), world()
        thin['environment']['fog_density'] = .001
        thick['environment']['fog_density'] = .2
        self.assertLess(checks.scene_haze(thin), checks.THIN_HAZE)
        self.assertGreater(checks.scene_haze(thick), checks.THIN_HAZE)

    def test_thin_haze_under_misty_sources_is_reported_and_warned(self):
        scene = world()
        scene['environment']['fog_density'] = .001
        report = checks.haze_report(scene, .8)
        self.assertEqual(set(report), {'source_mist', 'scene_haze', 'verdict'})
        self.assertEqual(report['verdict'], 'too_thin')
        plan = {'scene': scene}
        ids = [w['warning_id'] for w in gate.current_warnings(plan, gate_tests.CLEAN, None, {'source_mist': .8})]
        self.assertIn('frames:haze_thin', ids)
        self.assertNotIn('frames:haze_thin', [w['warning_id'] for w in gate.current_warnings(plan, gate_tests.CLEAN)])
        self.assertEqual(checks.haze_report(scene, 0.0)['verdict'], 'ok')
        self.assertIsNone(checks.haze_report(scene, None))

    def test_schema_states_the_mist_rule_once_per_tool(self):
        for name in ('rekindra_create_world', 'rekindra_revise_world', 'rekindra_preview'):
            self.assertIn('frames:haze_thin', SCHEMAS[name]['description'], name)


class CameraGrazeTests(unittest.TestCase):
    # The test world's camera passes (0.5, 2.35, 7) at 6 s, looking toward -z.
    def test_small_surface_on_the_camera_path_is_named(self):
        scene = world()
        scene['objects'].append(chip([.5, 2.35, 6.8]))
        found = checks.camera_graze_warnings(scene)
        self.assertEqual([w['warning_id'] for w in found], ['fragment:chip'])
        self.assertIn('Surface chip', found[0]['message'])
        self.assertIn('of the camera eye at', found[0]['message'])
        self.assertIn('fragment:chip', [w['warning_id'] for w in gate.current_warnings({'scene': scene}, gate_tests.CLEAN)])

    def test_scene_without_one_is_quiet(self):
        self.assertEqual(checks.camera_graze_warnings(world()), [])
        scene = world()
        scene['objects'].append(chip([0, 0, -3]))   # where the camera looks, far from its eye
        self.assertEqual(checks.camera_graze_warnings(scene), [])
        scene['objects'][-1] = chip([.5, 2.35, 7.6])   # behind the eye at its closest
        self.assertEqual(checks.camera_graze_warnings(scene), [])

    def test_instances_are_placed_and_named_by_index(self):
        scene = world()
        scene['objects'].append(chip([0, 0, 0], instances=[
            {'offset': [0, 0, -3], 'scale': [1, 1, 1]},
            {'offset': [.5, 2.35, 6.8], 'scale': [1, 1, 1], 'rotation': [0, 1.2, 0]}]))
        found = checks.camera_graze_warnings(scene)
        self.assertEqual([w['warning_id'] for w in found], ['fragment:chip'])
        self.assertIn('instance 1', found[0]['message'])


class ReportGateTests(gate_tests.ExportGateTests):
    def project_id(self):
        return self.project['project_id']

    def test_defects_carry_until_a_revise_answers_them(self):
        first = self.create()
        shown = self.preview(first)
        self.assertEqual(shown['defects'], [{'id': gate_tests.BOTTOM, 'detail': gate_tests.WARM,
                                             'carried': False, 'previews_survived': 0}])
        out = self.call('rekindra_revise_world', plan_id=first, edits=[{'field': 'title', 'value': 'Second'}])
        self.assertTrue(out['ok'], out)
        self.assertEqual(out['result']['flagged_defects'],
                         {'addressed': [], 'unaddressed': [gate_tests.BOTTOM], 'not_open': []})
        self.assertIn('flagged_defects.unaddressed', out['result']['next_step'])
        second = out['result']['plan_id']
        row = self.preview(second)['defects'][0]
        self.assertEqual((row['carried'], row['previews_survived']), (True, 1))
        self.assertNotIn('revise_said', row)

        out = self.call('rekindra_revise_world', plan_id=second, edits=[{'field': 'title', 'value': 'Third'}],
                        addresses=[{'id': gate_tests.BOTTOM, 'how': 'cooled the water colour'},
                                   {'id': 'palette:nowhere', 'how': 'nothing'}])
        self.assertTrue(out['ok'], out)
        said = out['result']['flagged_defects']
        self.assertEqual(said['addressed'], [{'id': gate_tests.BOTTOM, 'how': 'cooled the water colour'}])
        self.assertEqual((said['unaddressed'], said['not_open']), ([], ['palette:nowhere']))
        row = self.preview(out['result']['plan_id'])['defects'][0]
        self.assertEqual((row['previews_survived'], row['revise_said']), (2, 'cooled the water colour'))
        self.assertEqual(self.preview(out['result']['plan_id'], gate_tests.CLEAN).get('defects'), None)

    def test_clean_plans_keep_the_old_shapes(self):
        plan_id = self.create()
        shown = self.preview(plan_id, gate_tests.CLEAN)
        self.assertNotIn('defects', shown)
        record = json.loads((self.store._project(self.project_id()) / 'artifacts'
                             / f'{plan_id}-preview-record.json').read_text(encoding='utf-8'))
        self.assertEqual(set(record), {'plan_id', 'palette_drift'})
        out = self.call('rekindra_revise_world', plan_id=plan_id, edits=[{'field': 'title', 'value': 'Same'}])
        self.assertTrue(out['ok'], out)
        self.assertNotIn('flagged_defects', out['result'])

    def test_malformed_addresses_are_refused(self):
        plan_id = self.create()
        for bad in ('fix', [{'id': 'x'}], [{'id': 'x', 'how': ''}], [{'id': 'x', 'how': 'a'}, {'id': 'x', 'how': 'b'}],
                    [{'id': 'x', 'how': 'a', 'extra': 1}]):
            out = self.call('rekindra_revise_world', plan_id=plan_id, edits=[{'field': 'title', 'value': 'T'}],
                            addresses=bad)
            self.assertFalse(out['ok'], bad)

    def test_schema_advertises_addresses(self):
        field = SCHEMAS['rekindra_revise_world']['parameters']['properties']['addresses']
        self.assertEqual(field['items']['required'], ['id', 'how'])

    def test_preview_reports_object_motion_and_records_it(self):
        plan_id = self.create()
        frame = base64.b64encode(reliability.small_png()).decode()
        page = reliability.document([frame] * 6, self.plan(plan_id)['scene']['duration'])
        body = json.loads(page.split('application/json">', 1)[1].split('</script>')[0])
        body['result']['objectMotion'] = 0.0
        page = f'<html><body><script id="rekindra-review-result" type="application/json">{json.dumps(body)}</script></body></html>'
        data = page.encode()

        class Browser:
            returncode = 0

            def __init__(self, command, stdout=None, **options):
                stdout.write(data)
                stdout.flush()

            def poll(self):
                return 0

        with mock.patch.object(preview, 'find_browser', return_value='browser'), \
                mock.patch.object(preview.subprocess, 'Popen', Browser), \
                mock.patch.object(preview, 'measure_drift', return_value=gate_tests.CLEAN), \
                mock.patch.object(preview, 'measure_review_frames', return_value=reliability.LIVELY):
            out = preview.preview_scene(self.store, self.project_id(), plan_id)
        self.assertEqual(out['object_motion']['statement'], 'objects do not move on their own; only the camera moves')
        self.assertIn('only the camera moves', out['next_step'])
        self.assertNotIn('haze', out)   # no recovered palettes, so no mist reading
        ids = [w['warning_id'] for w in out['export_gate']['warnings']]
        self.assertEqual(ids, [])   # reported and tracked, never a gate warning
        self.assertEqual([d['id'] for d in out['defects']], ['frames:objects_still'])
        self.assertNotIn('export_blocked', json.dumps(self.export(plan_id)))
        answered = self.export(plan_id, [{'warning_id': 'frames:objects_still', 'reason': 'Only the camera is meant to move.'}])
        self.assertNotIn('export_blocked', json.dumps(answered))


# The gate's own tests run once, in their own file; only the helpers are borrowed here.
for _name in dir(gate_tests.ExportGateTests):
    if _name.startswith('test_') and _name not in ReportGateTests.__dict__:
        setattr(ReportGateTests, _name, None)


if __name__ == '__main__':
    unittest.main()
