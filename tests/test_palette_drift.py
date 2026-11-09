"""The preview's color drift report: what it measures, when it says to revise, and when it stays quiet."""
import unittest
from types import SimpleNamespace
from unittest import mock

try:
    from PIL import Image
except ImportError:
    Image = None

from test_plugin import plugin

from importlib import import_module

drift = import_module(f'{plugin.__name__}.rekindra_core.palette_drift')
recovery = import_module(f'{plugin.__name__}.rekindra_core.image_recovery')
png = import_module(f'{plugin.__name__}.rekindra_core.png')
tga = import_module(f'{plugin.__name__}.rekindra_core.tga')

PALETTE = [{'hex': '#28465F', 'location': 'bottom band', 'coverage': 26.6},
           {'hex': '#D99483', 'location': 'top band and middle', 'coverage': 20.8},
           {'hex': '#C68890', 'location': 'middle', 'coverage': 16.4}]
SOURCE = {'kind': 'source-palette', 'asset_ids': ['image-1'], 'palettes': [PALETTE]}
SCENE = {'objects': [{'id': 'water', 'color': '#28465F', 'color_high': '#28465F'}],
         'environment': {'sky_top': '#D99483'}}


def regions(top='#D99483', middle='#C68890', bottom='#28465F'):
    return [{'region': name, 'colors': [{'hex': color, 'coverage': 100.0}]}
            for name, color in (('top band', top), ('middle', middle), ('bottom band', bottom))]


def sheet(top, middle, bottom, label=(255, 0, 255)):
    """A 1280x1128 review sheet, six frames over rows of 376, with a loud label strip under each frame."""
    rgba = bytearray()
    for y in range(1128):
        inside = y % 376
        color = label if inside >= 360 else top if inside < 120 else middle if inside < 240 else bottom
        rgba += bytes(color + (255,)) * 1280
    return png.encode_png(tga.Raster(1280, 1128, bytes(rgba)))


class DriftReportTests(unittest.TestCase):
    def test_matching_render_is_ok(self):
        report = drift.drift_report(regions(), SOURCE, SCENE)
        self.assertEqual(report['status'], 'ok')
        self.assertEqual(report['source_asset_ids'], ['image-1'])
        self.assertEqual([row['delta_e'] for row in report['regions']], [0.0, 0.0, 0.0])
        self.assertTrue(all(row['flag'] is None for row in report['regions']))

    def test_warm_water_is_flagged_in_plain_words(self):
        report = drift.drift_report(regions(bottom='#6B4F4A'), SOURCE, SCENE)
        self.assertEqual(report['status'], 'drift')
        row = report['regions'][2]
        self.assertTrue(row['over_threshold'])
        self.assertEqual(row['flag'], 'water rendered #6B4F4A vs intended #28465F: lighting is shifting it warm; '
                                      'reduce warm sun/fill/ambient or adjust the material')

    def test_threshold_is_a_boundary_not_a_style(self):
        close, far = '#3C4F63', '#52413E'
        self.assertLess(drift.delta_e(close, '#28465F'), drift.SOURCE_THRESHOLD)
        self.assertGreater(drift.delta_e(far, '#28465F'), drift.SOURCE_THRESHOLD)
        self.assertEqual(drift.drift_report(regions(bottom=close), SOURCE, SCENE)['status'], 'ok')
        self.assertEqual(drift.drift_report(regions(bottom=far), SOURCE, SCENE)['status'], 'drift')

    def test_middle_band_gets_the_wider_margin(self):
        report = drift.drift_report(regions(middle='#765753'), SOURCE, SCENE)
        row = report['regions'][1]
        self.assertGreater(row['delta_e'], drift.SOURCE_THRESHOLD)
        self.assertLessEqual(row['delta_e'], drift.MIDDLE_THRESHOLD)
        self.assertEqual(report['status'], 'ok')

    def test_split_clusters_of_one_surface_count_as_one(self):
        band = [{'hex': '#55556D', 'coverage': 35.2}, {'hex': '#B49395', 'coverage': 34.6}, {'hex': '#AF9097', 'coverage': 23.4}]
        measured = [{'region': 'top band', 'colors': band}]
        row = drift.drift_report(measured, SOURCE, SCENE)['regions'][0]
        self.assertEqual((row['rendered'], row['rendered_coverage']), ('#B49395', 58.0))

    def test_same_input_same_report(self):
        band = [{'hex': '#55556D', 'coverage': 30.0}, {'hex': '#B49395', 'coverage': 30.0}, {'hex': '#28465F', 'coverage': 30.0}]
        measured = [{'region': 'bottom band', 'colors': band}]
        self.assertEqual(drift.drift_report(measured, SOURCE, SCENE), drift.drift_report(measured, SOURCE, SCENE))
        reordered = [{'region': 'bottom band', 'colors': list(reversed(band))}]
        self.assertEqual(drift.drift_report(measured, SOURCE, SCENE), drift.drift_report(reordered, SOURCE, SCENE))

    def test_text_evidence_supplies_the_target(self):
        colors = drift.text_colors([{'text': 'At dusk the sea was deep blue and the lamp burned green.'}])
        self.assertEqual([entry['surface'] for entry in colors], ['sea'])
        report = drift.drift_report(regions(bottom='#C89A50'), {'kind': 'text-evidence', 'colors': colors}, {'objects': []})
        self.assertEqual((report['status'], report['reference']), ('drift', 'text-evidence'))
        self.assertEqual([row['region'] for row in report['regions']], ['bottom band'])

    def test_reference_that_names_no_measured_region(self):
        report = drift.drift_report(regions(), {'kind': 'text-evidence', 'colors': []}, {'objects': []})
        self.assertEqual(report['status'], 'not_measured')


class MeasureDriftTests(unittest.TestCase):
    PLAN = {'scene': SCENE, 'source_ids': ['image-1']}

    @staticmethod
    def store(palette=PALETTE):
        artifact = {'asset_id': 'image-1', 'kind': 'recovered', 'palette': palette}
        return SimpleNamespace(status=lambda project_id: {'artifacts': [artifact]},
                               recover=mock.Mock(side_effect=recovery_error()))

    def test_inspection_camera_is_not_compared(self):
        with mock.patch.object(drift, 'measure_review_sheet') as measure:
            report = drift.measure_drift(self.store(), 'p', self.PLAN, b'png', review_camera={'eye': [0, 0, 1]})
        self.assertEqual(report['status'], 'not_measured')
        measure.assert_not_called()

    def test_measurement_failure_costs_only_the_report(self):
        with mock.patch.object(drift, 'measure_review_sheet', return_value=None):
            report = drift.measure_drift(self.store(), 'p', self.PLAN, b'png')
        self.assertEqual((report['status'], report['regions']), ('unavailable', []))

    def test_no_reference_says_so(self):
        store = self.store(palette=None)
        with mock.patch.object(drift, 'measure_review_sheet') as measure:
            report = drift.measure_drift(store, 'p', self.PLAN, b'png')
        self.assertEqual(report['status'], 'not_measured')
        measure.assert_not_called()

    def test_every_selected_source_can_supply_the_color(self):
        second = [{'hex': '#3F6B3A', 'location': 'bottom band', 'coverage': 40.0}]
        artifacts = [{'asset_id': 'image-1', 'kind': 'recovered', 'palette': PALETTE},
                     {'asset_id': 'image-2', 'kind': 'recovered', 'palette': second}]
        store = SimpleNamespace(status=lambda project_id: {'artifacts': artifacts}, recover=mock.Mock())
        plan = {'scene': SCENE, 'source_ids': ['image-1', 'image-2']}
        with mock.patch.object(drift, 'measure_review_sheet', return_value=regions(bottom='#3F6B3A')):
            report = drift.measure_drift(store, 'p', plan, b'png')
        self.assertEqual(report['status'], 'ok')
        self.assertEqual(report['source_asset_ids'], ['image-1', 'image-2'])
        self.assertEqual(report['regions'][2]['intended'], '#3F6B3A')
        store.recover.assert_not_called()

    def test_a_settled_empty_palette_is_not_measured_again(self):
        artifacts = [{'asset_id': 'image-1', 'kind': 'recovered', 'palette': PALETTE},
                     {'asset_id': 'image-2', 'kind': 'recovered', 'palette': None},
                     {'asset_id': 'image-3', 'kind': 'recovered', 'palette': []}]
        store = SimpleNamespace(status=lambda project_id: {'artifacts': artifacts}, recover=mock.Mock())
        plan = {'scene': SCENE, 'source_ids': ['image-1', 'image-2', 'image-3', 'never-recovered']}
        with mock.patch.object(drift, 'measure_review_sheet', return_value=regions()):
            report = drift.measure_drift(store, 'p', plan, b'png')
        store.recover.assert_not_called()
        self.assertEqual(report['source_asset_ids'], ['image-1'])

    def test_an_older_artifact_is_measured_and_a_failure_costs_that_source(self):
        artifacts = [{'asset_id': 'image-1', 'kind': 'recovered', 'palette': PALETTE},
                     {'asset_id': 'older', 'kind': 'recovered'}]
        store = SimpleNamespace(status=lambda project_id: {'artifacts': artifacts}, recover=mock.Mock(side_effect=OSError('busy')))
        plan = {'scene': SCENE, 'source_ids': ['image-1', 'older']}
        with mock.patch.object(drift, 'measure_review_sheet', return_value=regions()):
            report = drift.measure_drift(store, 'p', plan, b'png')
        store.recover.assert_called_once_with('p', 'older')
        self.assertEqual((report['status'], report['source_asset_ids']), ('ok', ['image-1']))

    def test_saved_palette_is_compared(self):
        with mock.patch.object(drift, 'measure_review_sheet', return_value=regions(bottom='#6B4F4A')):
            report = drift.measure_drift(self.store(), 'p', self.PLAN, b'png')
        self.assertEqual(report['status'], 'drift')


def recovery_error():
    return import_module(f'{plugin.__name__}.rekindra_core.projects').ProjectError('not an image')


@unittest.skipIf(Image is None, 'Pillow is not installed')
class ReviewSheetMeasurementTests(unittest.TestCase):
    def test_bands_ignore_the_time_labels_and_repeat(self):
        data = sheet((217, 148, 131), (198, 136, 144), (40, 70, 95))
        first = recovery.measure_review_sheet(data)
        self.assertEqual(first, recovery.measure_review_sheet(data))
        self.assertEqual([item['region'] for item in first], ['top band', 'middle', 'bottom band'])
        self.assertEqual([item['colors'][0]['hex'] for item in first], ['#D99483', '#C68890', '#28465F'])
        self.assertTrue(all(color['hex'] != '#FF00FF' for item in first for color in item['colors']))

    def test_wrong_shape_is_not_measured(self):
        self.assertIsNone(recovery.measure_review_sheet(png.encode_png(tga.Raster(4, 4, bytes(64)))))


if __name__ == '__main__':
    unittest.main()
