import ast
import contextlib
import importlib.util
import io
import json
import os
from pathlib import Path
import sys
import unittest

from rekindra_evidence import build_dossier, search_dossier

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from evidence_fixtures import assert_located, assert_matches_retained  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
SCRIPT = ROOT / 'examples' / 'evidence' / 'synthetic_collection.py'


def load_example():
    spec = importlib.util.spec_from_file_location('evidence_synthetic_collection', SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


example = load_example()


def group_ids(dossier):
    return [group['source_ids'] for group in dossier['duplicate_groups']]


class Example(unittest.TestCase):
    def setUp(self):
        self.records = example.records()
        self.dossier = build_dossier(self.records)

    def row(self, source_id):
        return next(item for item in self.dossier['sources'] if item['source_id'] == source_id)

    def test_matches_the_committed_expected_results(self):
        committed = json.loads((ROOT / 'examples' / 'evidence' / 'expected_results.json').read_text(encoding='utf-8'))
        self.assertEqual(json.loads(json.dumps(example.expected())), committed)

    def test_results_are_labelled_synthetic(self):
        self.assertTrue(example.expected()['synthetic'])
        self.assertIn('invented', SCRIPT.read_text(encoding='utf-8').splitlines()[1])

    def test_does_not_use_the_intake_package(self):
        for node in ast.walk(ast.parse(SCRIPT.read_text(encoding='utf-8'))):
            if isinstance(node, ast.Import):
                self.assertNotIn('rekindra_intake', [alias.name for alias in node.names])
            elif isinstance(node, ast.ImportFrom):
                self.assertNotEqual(node.module, 'rekindra_intake')

    def test_related_notes_are_found_with_direct_clues(self):
        result = search_dossier(self.dossier, 'harbour bell')
        self.assertLessEqual({'note-letter', 'note-logbook', 'data-cues'}, {m['source_id'] for m in result['matches']})

    def test_identical_bytes_under_different_names_group(self):
        self.assertEqual(group_ids(self.dossier), [['map-original', 'map-renamed']])

    def test_same_basename_different_content_does_not_group(self):
        self.assertIsNone(self.row('notes-draft-one')['duplicate_group'])
        self.assertIsNone(self.row('notes-draft-two')['duplicate_group'])
        self.assertNotEqual(self.row('notes-draft-one')['sha256'], self.row('notes-draft-two')['sha256'])

    def test_null_hashes_with_equal_sizes_do_not_group(self):
        self.assertIsNone(self.row('huge-log-1')['duplicate_group'])
        self.assertEqual(self.row('huge-log-1')['size_bytes'], self.row('huge-log-2')['size_bytes'])

    def test_each_status_is_present_and_reported(self):
        self.assertEqual(set(self.dossier['counts']['by_status']), {'ok', 'partial', 'unsupported', 'rejected'})
        self.assertEqual(self.row('image-photo')['inspection_status'], 'unsupported')
        self.assertEqual(self.row('binary-blob')['inspection_status'], 'rejected')
        self.assertEqual(self.row('damaged-note')['coverage']['undecoded_bytes'], 2)
        self.assertIs(self.row('empty-note')['coverage']['source_text_fully_retained'], True)

    def test_flagged_zip_stays_unverified_metadata(self):
        items = [item for item in self.dossier['evidence'] if item['source_id'] == 'archive-drafts']
        self.assertEqual(len(items), 4)
        self.assertEqual({item['provenance'] for item in items}, {'unverified_archive_metadata'})
        self.assertIs(self.row('archive-drafts')['coverage']['member_contents_inspected'], False)
        flagged = next(item for item in items if item['text'] == '../../outside.txt')
        self.assertEqual(flagged['archive_metadata']['safety_warnings'], ['path_traversal'])

    def test_hostile_note_stays_inert(self):
        text = next(i['text'] for i in self.dossier['evidence'] if i['source_id'] == 'hostile-note')
        self.assertEqual(text, example.ADVERSARIAL)
        self.assertEqual(self.dossier['status'], 'ok')
        self.assertEqual(self.row('note-letter')['warnings'], self.row('hostile-note')['warnings'])

    def test_every_locator_resolves_into_the_supplied_intake(self):
        for item in self.dossier['evidence']:
            assert_located(self, item, self.records)

    def test_every_search_result_resolves_to_retained_evidence(self):
        for query in example.QUERIES:
            with self.subTest(query=query):
                assert_matches_retained(self, search_dossier(self.dossier, query, limit=20), self.dossier)

    def test_no_match_keeps_its_caution(self):
        result = search_dossier(self.dossier, 'never written anywhere')
        self.assertEqual(result['status'], 'no_match')
        self.assertIn('does not show', result['notice'])

    def test_malformed_caller_data_is_rejected_with_the_expected_code(self):
        for name, (data, code) in example.malformed_cases().items():
            with self.subTest(name=name):
                result = build_dossier(data)
                self.assertEqual(result['status'], 'rejected')
                self.assertIn(code, [error['code'] for error in result['errors']])

    def test_command_line_summary_and_expected_output(self):
        for argv in ([], ['--print-expected']):
            output = io.StringIO()
            with contextlib.redirect_stdout(output):
                self.assertEqual(example.main(argv), 0)
            self.assertTrue(output.getvalue())


if __name__ == '__main__':
    unittest.main()
