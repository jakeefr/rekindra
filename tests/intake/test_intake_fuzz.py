import json
import os
import random
import sys
import unittest

from rekindra_intake import inspect_archive, inspect_text

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from intake_zip_builder import build, entry  # noqa: E402

ROUNDS = 3000
SPLICES = (b'\xff\xff', b'\x00\x00', b'PK', b'{"', b'[[', b'"', b'\xd8\x00', b'\xff\xff\xff\xff')


def mutate(data, rng):
    data = bytearray(data)
    for _ in range(rng.randint(1, 12)):
        if not data:
            data.append(rng.randrange(256))
        index = rng.randrange(len(data))
        action = rng.randrange(4)
        if action == 0:
            data[index] = rng.randrange(256)
        elif action == 1:
            data[index:index] = rng.randbytes(rng.randint(1, 8))
        elif action == 2:
            del data[index:index + rng.randint(1, 8)]
        else:
            data[index:index + 2] = rng.choice(SPLICES)
    return bytes(data)


class SeededFuzz(unittest.TestCase):
    """Malformed content must produce an encodable envelope, never an exception."""

    def assertSurvives(self, inspector, data, name):
        try:
            result = inspector(data, name)
            json.dumps(result, allow_nan=False, ensure_ascii=False).encode('utf-8')
        except Exception as exc:  # noqa: BLE001 - any escape is the failure under test
            self.fail(f'{inspector.__name__} raised {exc!r} for {name} {data[:80]!r}')

    def test_mutated_archives(self):
        rng = random.Random(20261105)
        seed = build([entry('a.txt', b'hello', extra=b'\x75\x70\x04\x00abcd'), entry('dir/'),
                      entry('../x', b'y', method=8, uncompressed=9)], comment=b'hey')
        for _ in range(ROUNDS):
            self.assertSurvives(inspect_archive, mutate(seed, rng), 'f.zip')

    def test_mutated_text_formats(self):
        rng = random.Random(20261106)
        seeds = [(b'# Title\n```\n# x\n```\n- item\n', 'a.md'), (b'{"a": [1, {"b": 2.5e3}], "c": "\\ud83d\\ude00"}', 'a.json'),
                 (b'a,"b,c"\n"d\ne",=f\n', 'a.csv'), (b'\xff\xfe' + 'mixed text\n'.encode('utf-16-le'), 'a.txt')]
        for _ in range(ROUNDS):
            data, name = rng.choice(seeds)
            self.assertSurvives(inspect_text, mutate(data, rng), name)

    def test_random_bytes(self):
        rng = random.Random(20261107)
        for _ in range(ROUNDS):
            data = rng.randbytes(rng.randint(0, 40))
            self.assertSurvives(inspect_text, data, rng.choice(('a.txt', 'a.md', 'a.json', 'a.csv')))
            self.assertSurvives(inspect_archive, data, 'a.zip')


if __name__ == '__main__':
    unittest.main()
