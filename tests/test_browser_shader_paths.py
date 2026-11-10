"""Compile and pixel checks for the optional renderer paths on the software renderer (SwiftShader).

Each script forces SwiftShader, asserts every shader compiles and links with no GL error, and checks the feature's
visible effect against a control. Skipped when Node, Playwright or an installed Chrome is not available.
"""
import os
from pathlib import Path
import shutil
import subprocess
import sys
import unittest

ROOT = Path(__file__).resolve().parents[1]
CHROME_MISSING = ("Chromium distribution 'chrome' is not found", "Executable doesn't exist")


def playwright_available():
    if shutil.which('node') is None:
        return False
    probe = subprocess.run(['node', '-e', "require.resolve(process.env.REKINDRA_PLAYWRIGHT_PATH||'playwright')"],
                           cwd=ROOT, capture_output=True, timeout=30)
    return probe.returncode == 0


@unittest.skipUnless(playwright_available(), 'Node with Playwright is not available (set REKINDRA_PLAYWRIGHT_PATH)')
class BrowserShaderPathTests(unittest.TestCase):
    def run_script(self, name):
        env = dict(os.environ)
        env.pop('REKINDRA_BROWSER_OUTPUT', None)
        env.setdefault('REKINDRA_PYTHON', sys.executable)
        result = subprocess.run(['node', str(ROOT / 'scripts' / name)], cwd=ROOT, env=env,
                                capture_output=True, text=True, timeout=120)
        output = result.stdout + result.stderr
        if result.returncode != 0 and any(marker in output for marker in CHROME_MISSING):
            self.skipTest('Installed Chrome is not available for Playwright')
        self.assertEqual(result.returncode, 0, output[-4000:])

    def test_atmosphere(self):
        self.run_script('browser_atmosphere_test.cjs')

    def test_foliage(self):
        self.run_script('browser_foliage_test.cjs')

    def test_soft(self):
        self.run_script('browser_soft_test.cjs')

    def test_material_image(self):
        self.run_script('browser_material_image_test.cjs')

    def test_constructs(self):
        self.run_script('browser_constructs_test.cjs')


if __name__ == '__main__':
    unittest.main()
