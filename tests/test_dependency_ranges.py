"""Our declared dependency ranges must keep including what Hermes installs.

A plugin cannot move a Hermes pin, and a range that excludes it gets the plugin disabled.
"""
import json
import os
from pathlib import Path
import re
import unittest

ROOT = Path(__file__).resolve().parents[1]
# Hermes's own pins when these ranges were set. Raising them is the signal to recheck.
HERMES_PINS = {'pypdf': '6.21.4', 'pillow': '13.0.0'}
_CLAUSE = re.compile(r'^(>=|<=|==|<|>)(\d+(?:\.\d+)*)$')
_ENTRY = re.compile(r'^([A-Za-z0-9][A-Za-z0-9._-]*)(.+)$')
_DIST_INFO = re.compile(r'^(pillow|pypdf)-(\d+(?:\.\d+)*)\.dist-info$', re.I)


def declared(text=None):
    """The python_dependencies of plugin.yaml as {lower-case name: specifier}."""
    text = (ROOT / 'plugin.yaml').read_text(encoding='utf-8') if text is None else text
    found, inside = {}, False
    for line in text.splitlines():
        if line.startswith('python_dependencies:'):
            inside = True
        elif inside and line.startswith('  - '):
            match = _ENTRY.match(line[4:].strip())
            found[match.group(1).lower()] = match.group(2).strip()
        elif inside:
            break
    return found


def _version(text):
    parts = [int(part) for part in text.split('.')]
    return tuple(parts + [0] * (4 - len(parts)))


def allows(specifier, version):
    """Whether a comma-separated specifier admits a release version. Unknown operators raise."""
    have = _version(version)
    for clause in specifier.split(','):
        match = _CLAUSE.match(clause.strip())
        if match is None:
            raise ValueError(f'Unsupported requirement clause: {clause!r}')
        want = _version(match.group(2))
        if not {'>=': have >= want, '<=': have <= want, '==': have == want,
                '<': have < want, '>': have > want}[match.group(1)]:
            return False
    return True


def installed_versions():
    """Versions in the newest Hermes package environment, or None if it cannot be found."""
    home = os.environ.get('HERMES_HOME')
    if not home:
        return None
    facts = sorted(Path(home).glob('installs/*/facts.json'), key=lambda p: p.stat().st_mtime)
    if not facts:
        return None
    try:
        environment = json.loads(facts[-1].read_text(encoding='utf-8'))['packages']['venv']['environment']
    except (OSError, ValueError, KeyError, TypeError):
        return None
    roots = [Path(environment) / 'Lib' / 'site-packages', *Path(environment).glob('lib/python*/site-packages')]
    found = {}
    for root in roots:
        if root.is_dir():
            for entry in root.iterdir():
                match = _DIST_INFO.match(entry.name)
                if match:
                    found[match.group(1).lower()] = match.group(2)
    return found or None


class DependencyRangeTests(unittest.TestCase):
    def test_checker_rejects_a_range_that_excludes_the_version(self):
        self.assertTrue(allows('>=6.21.4,<7', '6.21.4'))
        self.assertTrue(allows('>=6.21.4,<7', '6.30'))
        self.assertFalse(allows('>=6.21.4,<7', '7.0.0'))
        self.assertFalse(allows('>=6.22,<7', '6.21.4'))
        self.assertFalse(allows('==6.16.1', '6.21.4'))
        with self.assertRaises(ValueError):
            allows('~=6.21', '6.21.4')

    def test_every_entry_is_bounded_above(self):
        for name, specifier in declared().items():
            with self.subTest(name=name):
                self.assertRegex(specifier, r'(^|,)\s*(<|==)')

    def test_declared_ranges_include_the_recorded_hermes_pins(self):
        ranges = declared()
        self.assertEqual(set(ranges), set(HERMES_PINS))
        for name, version in HERMES_PINS.items():
            with self.subTest(name=name):
                self.assertTrue(allows(ranges[name], version), f'{name} {ranges[name]} excludes Hermes {version}')

    def test_declared_ranges_include_the_installed_hermes_versions(self):
        found = installed_versions()
        if found is None:
            self.skipTest('no Hermes install is reachable through HERMES_HOME')
        ranges = declared()
        for name, version in found.items():
            with self.subTest(name=name):
                self.assertTrue(allows(ranges[name], version), f'{name} {ranges[name]} excludes installed {version}')


if __name__ == '__main__':
    unittest.main()
