"""Regression tests: shortened output must be visible at the result level."""
import json
import os
import sys
import unittest

from rekindra_intake import inspect_archive, inspect_text

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from intake_zip_builder import build, entry  # noqa: E402

LONG = 'h' * 200


def codes(result):
    return [item['code'] for item in result['warnings']]


class ShortenedStructure(unittest.TestCase):
    def test_long_heading_warns(self):
        result = inspect_text(f'# {LONG}\n'.encode(), 'a.md')
        self.assertEqual(len(result['facts']['headings'][0]['text']), 80)
        self.assertIn('structure_truncated', codes(result))

    def test_long_json_key_warns(self):
        result = inspect_text(json.dumps({LONG: 1}).encode(), 'a.json')
        self.assertEqual(len(result['facts']['top_level_keys'][0]), 80)
        self.assertIn('structure_truncated', codes(result))

    def test_items_at_the_limit_do_not_warn(self):
        self.assertNotIn('structure_truncated', codes(inspect_text(f'# {"h" * 80}\n'.encode(), 'a.md')))
        self.assertNotIn('structure_truncated', codes(inspect_text(json.dumps({'k' * 80: 1}).encode(), 'a.json')))

    def test_item_cut_by_the_shared_budget_warns(self):
        data = ''.join(f'# {"h" * 75}{i:05d}\n' for i in range(40)).encode()
        result = inspect_text(data, 'a.md')
        self.assertIn('structure_truncated', codes(result))


class ShortenedEntryNames(unittest.TestCase):
    def test_long_name_warns_at_the_result_level(self):
        result = inspect_archive(build([entry('n' * 900)]), 'a.zip')
        self.assertTrue(result['facts']['entries'][0]['name_truncated'])
        self.assertIn('entry_name_truncated', codes(result))
        self.assertEqual(result['status'], 'ok')

    def test_name_at_the_limit_does_not_warn(self):
        self.assertNotIn('entry_name_truncated', codes(inspect_archive(build([entry('n' * 512)]), 'a.zip')))


if __name__ == '__main__':
    unittest.main()
