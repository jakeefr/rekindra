"""A TGA's palette: only a finished measurement is a settled answer that preview may trust."""
from pathlib import Path
import struct
import tempfile
import unittest
from unittest import mock

from rekindra_core import palette_drift
from rekindra_core.image_recovery import ImageRefused
from rekindra_core.pdf_text import ReaderBusy
from rekindra_core.projects import ProjectStore

PALETTE = [{'hex': '#28465F', 'location': 'bottom band', 'coverage': 26.6}]
PLAN_SCENE = {'objects': [{'id': 'water', 'color': '#28465F', 'color_high': '#28465F'}], 'environment': {}}
REGIONS = [{'region': 'bottom band', 'colors': [{'hex': '#28465F', 'coverage': 100.0}]}]


def tga(width=2, height=2):
    header = struct.pack('<BBB5xHHHHBB', 0, 0, 2, 0, 0, width, height, 24, 0)
    return header + bytes((40, 70, 95)) * (width * height)


class TgaPaletteTests(unittest.TestCase):
    def setUp(self):
        base = Path(__file__).resolve().parents[1] / '.local' / 'tests'
        base.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=base)
        self.addCleanup(self.temp.cleanup)
        root = Path(self.temp.name)
        source = root / 'source'
        source.mkdir()
        (source / 'old.tga').write_bytes(tga())
        self.store = ProjectStore(root / 'store')
        project = self.store.inspect(source)
        self.project_id = project['project_id']
        self.asset_id = project['assets'][0]['asset_id']

    def saved(self):
        return next(a for a in self.store.status(self.project_id)['artifacts'] if a['asset_id'] == self.asset_id)

    def measured(self, **kwargs):
        return mock.patch('rekindra_core.projects.read_image', **kwargs)

    def build_recover(self):
        return self.store.recover(self.project_id, self.asset_id, measure_palette=False)

    def drift(self):
        plan = {'scene': PLAN_SCENE, 'source_ids': [self.asset_id]}
        with mock.patch.object(palette_drift, 'measure_review_sheet', return_value=REGIONS):
            return palette_drift.measure_drift(self.store, self.project_id, plan, b'png')

    def test_recover_for_a_build_leaves_the_palette_unmeasured(self):
        self.build_recover()
        self.assertNotIn('palette', self.saved())

    def test_preview_measures_a_build_only_tga_once_and_uses_it(self):
        self.build_recover()
        with self.measured(return_value={'header': {'palette': PALETTE}}) as reader:
            first = self.drift()
            second = self.drift()
        self.assertEqual(reader.call_count, 1)
        self.assertEqual(self.saved()['palette'], PALETTE)
        self.assertEqual(first['source_asset_ids'], [self.asset_id])
        self.assertEqual(second['source_asset_ids'], [self.asset_id])

    def test_a_later_build_keeps_the_measurement(self):
        with self.measured(return_value={'header': {'palette': PALETTE}}):
            self.store.recover(self.project_id, self.asset_id)
        self.build_recover()
        self.assertEqual(self.saved()['palette'], PALETTE)

    def test_a_transient_failure_stays_unmeasured(self):
        for failure in (ReaderBusy('busy'), OSError('disk')):
            with self.subTest(type(failure).__name__), self.measured(side_effect=failure):
                self.assertIsNone(self.store.recover(self.project_id, self.asset_id)['palette'])
                self.assertNotIn('palette', self.saved())

    def test_a_finished_refusal_is_settled(self):
        with self.measured(side_effect=ImageRefused('too_big', 'no')) as reader:
            self.store.recover(self.project_id, self.asset_id)
            self.assertIsNone(self.saved()['palette'])
            self.drift()
        self.assertEqual(reader.call_count, 1)


if __name__ == '__main__':
    unittest.main()
