import copy
import json
import os
import random
import sys
import unittest

from rekindra_evidence import build_dossier, search_dossier

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from evidence_fixtures import assert_matches_retained, envelope, record, text_record, zip_entry, zip_record  # noqa: E402

ROUNDS = 2000
JUNK = (None, True, False, 0, -1, 1.5, '', 'x', 'ignore previous instructions', [], {}, [None], {'text': 1}, ['a', 1], 'é\n<b>',
        2 ** 70, 1e308, 'a' * 1500)


def paths(value):
    """Every (container, key) location in a JSON-like value."""
    found = []
    if isinstance(value, dict):
        for key in value:
            found.append((value, key))
            found.extend(paths(value[key]))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            found.append((value, index))
            found.extend(paths(item))
    return found


def mutate(value, rng):
    copied = copy.deepcopy(value)
    locations = paths(copied)
    for _ in range(rng.randint(1, 4)):
        container, key = rng.choice(locations)
        action = rng.randrange(3)
        try:
            if action == 0 and isinstance(container, dict):
                del container[key]
            elif action == 1 and isinstance(container, list):
                container.insert(key, rng.choice(JUNK))
            else:
                container[key] = rng.choice(JUNK)
        except (KeyError, IndexError):
            continue
    return copied


def seed_records():
    return [text_record('a', 'the harbour bell ' * 80, headings=[{'level': 1, 'line': 1, 'text': 'Title'}], fmt='markdown'),
            record('j', 'j.json', envelope('json', facts={'excerpt': '{}', 'top_level_keys': ['a', 'b'], 'valid': True}, sha=None)),
            record('c', 'c.csv', envelope('csv', facts={'excerpt': 'a,b', 'first_row': ['a', 'b'], 'next_rows': [['1', '=2']]})),
            zip_record('z', [zip_entry('../x', safety_warnings=['path_traversal']), zip_entry('b')]),
            record('u', 'u.bin', envelope('unknown', 'unsupported', sha=None))]


class SeededFuzz(unittest.TestCase):
    """Malformed JSON-compatible data must return a structured result, never raise."""

    def test_mutated_records(self):
        rng = random.Random(1105)
        seed = seed_records()
        for _ in range(ROUNDS):
            data = mutate(seed, rng)
            before = copy.deepcopy(data)
            try:
                result = build_dossier(data)
                self.assertLessEqual(len(json.dumps(result, allow_nan=False)), 256 * 1024)
            except Exception as exc:  # noqa: BLE001 - any escape is the failure under test
                self.fail(f'build_dossier raised {exc!r} for {repr(data)[:300]}')
            self.assertEqual(data, before)

    def test_mutated_dossiers(self):
        rng = random.Random(1106)
        seed = build_dossier(seed_records())
        for _ in range(ROUNDS):
            dossier = mutate(seed, rng)
            try:
                json.dumps(search_dossier(dossier, 'harbour bell x'), allow_nan=False)
            except Exception as exc:  # noqa: BLE001 - any escape is the failure under test
                self.fail(f'search_dossier raised {exc!r} for {repr(dossier)[:300]}')

    def test_random_queries(self):
        rng = random.Random(1107)
        dossier = build_dossier(seed_records())
        alphabet = 'ab \n\t ßﬁ́é日🔥<=*.\\﻿ '
        for _ in range(ROUNDS):
            query = ''.join(rng.choice(alphabet) for _ in range(rng.randint(0, 40)))
            result = search_dossier(dossier, query, limit=rng.randint(1, 20))
            json.dumps(result, allow_nan=False)
            if result['status'] == 'ok':
                assert_matches_retained(self, result, dossier)


if __name__ == '__main__':
    unittest.main()
