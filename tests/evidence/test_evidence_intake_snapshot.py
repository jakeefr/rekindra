"""Checks real intake output without importing intake.

intake_output_snapshot.json is saved output from the intake code, run once over
invented inputs, so these tests need no package beyond rekindra_evidence.
"""
import json
import os
from pathlib import Path
import sys
import unittest

from rekindra_evidence import build_dossier, search_dossier

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from evidence_fixtures import assert_located  # noqa: E402

SNAPSHOT = Path(__file__).resolve().parent / 'intake_output_snapshot.json'


class RealIntakeOutput(unittest.TestCase):
    def setUp(self):
        saved = json.loads(SNAPSHOT.read_text(encoding='utf-8'))
        self.assertTrue(saved['synthetic'])
        self.records = saved['records']
        self.dossier = build_dossier(self.records)

    def test_saved_results_build_and_every_locator_resolves(self):
        self.assertEqual(self.dossier['status'], 'ok')
        self.assertGreater(len(self.dossier['evidence']), 5)
        for item in self.dossier['evidence']:
            assert_located(self, item, self.records)
        json.dumps(self.dossier, allow_nan=False)

    def test_each_intake_status_is_represented(self):
        self.assertEqual(set(self.dossier['counts']['by_status']), {'ok', 'partial', 'unsupported', 'rejected'})

    def test_duplicates_search_and_flags(self):
        self.assertEqual([group['source_ids'] for group in self.dossier['duplicate_groups']], [['copy', 'text']])
        self.assertEqual(search_dossier(self.dossier, 'harbour')['status'], 'ok')
        entry = next(item for item in self.dossier['evidence'] if item['kind'] == 'archive_entry_name')
        self.assertEqual(entry['archive_metadata']['safety_warnings'], ['path_traversal'])

    def test_partial_text_reports_its_undecoded_bytes(self):
        row = next(item for item in self.dossier['sources'] if item['source_id'] == 'cut')
        self.assertEqual(row['coverage']['undecoded_bytes'], 2)
        self.assertIs(row['coverage']['source_text_fully_retained'], False)


if __name__ == '__main__':
    unittest.main()
