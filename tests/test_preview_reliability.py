"""A preview that cannot run says so and stops the agent; empty or frozen frames block export; frames come singly."""
import base64
import json
import unittest
from importlib import import_module
from pathlib import Path
from unittest import mock

try:
    from PIL import Image
except ImportError:
    Image = None

import test_export_gate as gate_tests
from test_palette_drift import sheet

plugin = gate_tests.plugin
gate = gate_tests.gate
preview = gate_tests.preview_module
recovery = import_module(f'{plugin.__name__}.rekindra_core.image_recovery')
png = import_module(f'{plugin.__name__}.rekindra_core.png')
tga = import_module(f'{plugin.__name__}.rekindra_core.tga')
SceneError = import_module(f'{plugin.__name__}.rekindra_core.scenes').SceneError
reconstruct = import_module(f'{plugin.__name__}.rekindra_core.reconstruct')
GAP_KEYS = ('skipped_at_inspect', 'not_recovered', 'intake', 'partial_images', 'unplaced_images', 'unplaced_text')

LIVELY = {'spread': [80, 82, 81, 85, 83, 80], 'change': [1.3, 2.1, 1.8, 1.5, 1.9]}
EMPTY = {'spread': [0, 1, 0, 2, 0, 0], 'change': [0.0, 0.1, 0.0, 0.0, 0.0]}
STILL = {'spread': [80, 80, 80, 80, 80, 80], 'change': [0.0, 0.05, 0.0, 0.1, 0.0]}


def small_png(width=640, height=360):
    return png.encode_png(tga.Raster(width, height, bytes(width * height * 4)))


def document(frames=None, duration=6):
    result = {'kind': 'rendered-frame-review', 'times': [(i + .5) * duration / 6 for i in range(6)],
              'png': base64.b64encode(sheet((1, 2, 3), (4, 5, 6), (7, 8, 9))).decode()}
    if frames is not None:
        result['frames'] = frames
    body = json.dumps({'ok': True, 'result': result})
    return f'<html><body><script id="rekindra-review-result" type="application/json">{body}</script></body></html>'


class FrameWarningTests(unittest.TestCase):
    def test_lively_frames_raise_nothing(self):
        self.assertEqual(gate.frame_warnings(LIVELY), [])

    def test_flat_frames_are_empty(self):
        found = gate.frame_warnings(EMPTY)
        self.assertEqual([w['warning_id'] for w in found], ['frames:empty'])
        self.assertIn('show nothing', found[0]['message'])

    def test_identical_frames_are_motionless(self):
        found = gate.frame_warnings(STILL)
        self.assertEqual([w['warning_id'] for w in found], ['frames:motionless'])
        self.assertIn('still', found[0]['message'])

    def test_unmeasured_frames_never_block(self):
        for value in (None, {}, {'spread': [], 'change': []}, {'spread': ['x'] * 6, 'change': [None] * 5}, 'frames'):
            self.assertEqual(gate.frame_warnings(value), [], value)

    def test_dark_but_structured_scene_is_not_empty(self):
        # A night scene measured in calibration: low spread, real motion.
        self.assertEqual(gate.frame_warnings({'spread': [20, 24, 31, 28, 22, 20], 'change': [4.6, 5.0, 8.3, 6.1, 4.9]}), [])


class FrameGateTests(gate_tests.ExportGateTests):
    def test_empty_preview_blocks_export_until_answered(self):
        plan_id = self.create()
        shown = gate.preview_gate(self.store, self.project['project_id'], self.plan(plan_id), gate_tests.CLEAN, None, EMPTY)
        self.assertEqual([w['warning_id'] for w in shown['warnings']], ['frames:empty'])
        message = self.assertBlocked(self.export(plan_id))
        self.assertIn('frames:empty', message)
        out = self.export(plan_id, [{'warning_id': 'frames:empty', 'reason': 'a deliberate fade to black throughout'}])
        self.assertTrue(out['ok'], out)
        self.assertEqual(out['result']['status'], 'acknowledged')

    def test_motionless_preview_blocks_export(self):
        plan_id = self.create()
        gate.preview_gate(self.store, self.project['project_id'], self.plan(plan_id), gate_tests.CLEAN, None, STILL)
        self.assertIn('frames:motionless', self.assertBlocked(self.export(plan_id)))

    def test_lively_preview_is_clear_and_old_records_still_work(self):
        plan_id = self.create()
        gate.preview_gate(self.store, self.project['project_id'], self.plan(plan_id), gate_tests.CLEAN, None, LIVELY)
        self.assertEqual(self.export(plan_id)['result']['status'], 'clear')
        other = self.create()
        gate.preview_gate(self.store, self.project['project_id'], self.plan(other), gate_tests.CLEAN, None)
        self.assertEqual(self.export(other)['result']['status'], 'clear')

    def test_missing_record_says_only_the_tool_can_make_it(self):
        message = self.assertBlocked(self.export(self.create()))
        self.assertIn('Only rekindra_preview can make that record', message)
        self.assertIn('never write one another way', message)
        self.assertIn('if its error says to stop, stop and tell the user', message)

    def test_preview_writes_six_frames_and_records_their_measurement(self):
        plan_id = self.create()
        frame = base64.b64encode(small_png()).decode()
        body = document([frame] * 6, self.plan(plan_id)['scene']['duration']).encode()

        class Browser:
            returncode = 0

            def __init__(self, command, stdout=None, **options):
                stdout.write(body)
                stdout.flush()

            def poll(self):
                return 0

        with mock.patch.object(preview, 'find_browser', return_value='browser'), \
                mock.patch.object(preview.subprocess, 'Popen', Browser), \
                mock.patch.object(preview, 'measure_drift', return_value=gate_tests.CLEAN), \
                mock.patch.object(preview, 'measure_review_frames', return_value=STILL) as measured:
            out = preview.preview_scene(self.store, self.project['project_id'], plan_id)
        measured.assert_called_once()
        self.assertEqual([f['time_seconds'] for f in out['frames']], out['times_seconds'])
        for item in out['frames']:
            self.assertEqual(Path(item['path']).read_bytes(), small_png())
        self.assertIn('frames:motionless', [w['warning_id'] for w in out['export_gate']['warnings']])
        self.assertIn('frames:motionless', self.assertBlocked(self.export(plan_id)))

    def test_inspection_preview_is_not_measured_for_the_gate(self):
        plan_id = self.create()
        body = document(None, self.plan(plan_id)['scene']['duration']).encode()

        class Browser:
            returncode = 0

            def __init__(self, command, stdout=None, **options):
                stdout.write(body)
                stdout.flush()

            def poll(self):
                return 0

        camera = {'eye': [0, 30, 0.1], 'target': [0, 0, 0], 'fov': 50}
        with mock.patch.object(preview, 'find_browser', return_value='browser'), \
                mock.patch.object(preview.subprocess, 'Popen', Browser), \
                mock.patch.object(preview, 'measure_review_frames') as measured:
            out = preview.preview_scene(self.store, self.project['project_id'], plan_id, review_camera=camera)
        measured.assert_not_called()
        self.assertEqual(out['frames'], [])
        self.assertIsNone(out['export_gate'])


# The gate's own tests run once, in their own file; only the helpers are borrowed here.
for _name in dir(gate_tests.ExportGateTests):
    if _name.startswith('test_') and _name not in FrameGateTests.__dict__:
        setattr(FrameGateTests, _name, None)


class PageWordingTests(unittest.TestCase):
    def test_reader_codes_and_tool_hints_are_reworded_for_the_page(self):
        self.assertEqual(reconstruct._plain('unsupported_image_format; run rekindra_recover on it'), 'unsupported image format')
        self.assertEqual(reconstruct._plain('photo_01.tga'), 'photo 01.tga')   # why file names bypass it

    def test_gap_rows_keep_file_names_and_reword_codes(self):
        class Page:
            def __init__(self):
                self.parts = []

            def add(self, html):
                self.parts.append(html)

            @staticmethod
            def text(value):
                return str(value)

        page = Page()
        gaps = {key: [] for key in GAP_KEYS}
        gaps['inventory_truncated'] = False
        gaps['skipped_at_inspect'] = [{'source_path': 'my_old_notes.xyz', 'reason': 'unsupported_file_type'}]
        gaps['not_recovered'] = [{'source_path': 'a_b.zip', 'reason': 'not recovered; run rekindra_recover on it'}]
        reconstruct._render_gaps(page, gaps)
        html = ''.join(page.parts)
        self.assertIn('<code>my_old_notes.xyz</code>', html)
        self.assertIn('unsupported file type', html)
        self.assertIn('<code>a_b.zip</code>', html)
        self.assertNotIn('rekindra_recover', html)

    def test_unnamed_model_is_said_in_words_not_as_a_field_value(self):
        source = (gate_tests.ROOT / 'runtime' / 'player.js').read_text(encoding='utf-8')
        self.assertIn('Which model it was is not recorded.', source)
        self.assertIn("v!=='not-attested'", source)


class PreviewOutputTests(unittest.TestCase):
    def test_empty_output_when_elevated_names_the_cause_and_the_fix(self):
        with mock.patch.object(preview, '_elevated', return_value=True):
            with self.assertRaises(SceneError) as caught:
                preview._decode_review('  \n', 6)
        text = str(caught.exception)
        self.assertIn('running as Administrator', text)
        self.assertIn('normal (not "Run as administrator") PowerShell', text)
        self.assertIn('Stop and tell the user', text)
        self.assertIn('do not edit skill or plugin files', text)

    def test_empty_output_unelevated_still_stops_the_agent(self):
        with mock.patch.object(preview, '_elevated', return_value=False):
            with self.assertRaises(SceneError) as caught:
                preview._decode_review('', 6)
        self.assertNotIn('Administrator', str(caught.exception))
        self.assertIn('Stop and tell the user', str(caught.exception))

    def test_missing_browser_stops_the_agent(self):
        with mock.patch.dict(preview.os.environ, {'REKINDRA_BROWSER': 'not-a-path'}):
            with self.assertRaises(SceneError) as caught:
                preview.find_browser()
        self.assertIn('Stop and tell the user', str(caught.exception))

    def test_one_sheet_read_serves_both_measurements_and_failures_are_not_kept(self):
        header = {'kind': 'ok', 'regions': None, 'frames': dict(STILL, spread=[80] * 6, change=[0, 0, 0, 0, 0])}
        with mock.patch.object(recovery, '_LAST_REVIEW', (None, None)), \
                mock.patch.object(recovery, '_read_review_header', side_effect=[None, header]) as read:
            self.assertIsNone(recovery.measure_review_frames(b'sheet'))
            self.assertEqual(recovery.measure_review_frames(b'sheet')['spread'], [80] * 6)
            self.assertIsNone(recovery.measure_review_sheet(b'sheet'))
        self.assertEqual(read.call_count, 2)

    def test_browser_is_told_not_to_drop_elevation(self):
        source = (gate_tests.ROOT / 'rekindra_core' / 'preview.py').read_text(encoding='utf-8')
        self.assertIn("'--do-not-de-elevate'", source)

    def test_six_small_frames_are_returned(self):
        frame = base64.b64encode(small_png()).decode()
        sheet_png, times, frames = preview._decode_review(document([frame] * 6), 6)
        self.assertEqual(len(frames), 6)
        self.assertEqual(frames[0], small_png())
        self.assertEqual(preview._decode_result(document([frame] * 6), 6), (sheet_png, times))

    def test_unusable_frames_are_dropped_without_failing_the_preview(self):
        good = base64.b64encode(small_png()).decode()
        wrong_size = base64.b64encode(small_png(320, 180)).decode()
        for frames in (None, [good] * 5, [good] * 5 + [wrong_size], [good] * 5 + ['!!'], [good] * 5 + [7], 'frames'):
            self.assertEqual(preview._decode_review(document(frames), 6)[2], [], frames)

    def test_tool_description_tells_the_agent_to_stop_on_failure(self):
        text = plugin.schemas.SCHEMAS['rekindra_preview']['description']
        self.assertIn('When its error says to stop, stop and tell the user', text)
        self.assertIn('after any other error you may retry or revise the scene', text)
        self.assertIn('never render, measure or record a preview any other way', text)
        self.assertIn('do not retry it', text)


@unittest.skipIf(Image is None, 'Pillow is not installed')
class ReviewFrameMeasurementTests(unittest.TestCase):
    def test_flat_sheet_measures_as_empty_and_still(self):
        stats = recovery.measure_review_frames(sheet((9, 9, 9), (9, 9, 9), (9, 9, 9)))
        self.assertEqual(stats['spread'], [0] * 6)
        self.assertEqual(stats['change'], [0] * 5)
        self.assertEqual([w['warning_id'] for w in gate.frame_warnings(stats)], ['frames:empty'])

    def test_banded_static_sheet_measures_as_motionless(self):
        stats = recovery.measure_review_frames(sheet((217, 148, 131), (198, 136, 144), (40, 70, 95)))
        self.assertGreater(min(stats['spread']), 50)
        self.assertEqual([w['warning_id'] for w in gate.frame_warnings(stats)], ['frames:motionless'])

    def test_wrong_shape_is_not_measured(self):
        self.assertIsNone(recovery.measure_review_frames(png.encode_png(tga.Raster(4, 4, bytes(64)))))


if __name__ == '__main__':
    unittest.main()
