import ast
import contextlib
import hashlib
import importlib.util
import io
import json
import os
import struct
import tempfile
import unittest
import zipfile
from pathlib import Path

from rekindra_intake import inspect_archive, inspect_text

HERE = Path(__file__).resolve().parent
EXAMPLES = HERE.parents[1] / 'examples' / 'intake'
SCRIPT = EXAMPLES / 'generate_source_pack.py'


def load_generator():
    spec = importlib.util.spec_from_file_location('intake_source_pack_generator', SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


generator = load_generator()


def tree(root):
    return sorted(p.relative_to(root).as_posix() for p in Path(root).rglob('*'))


class Reproducible(unittest.TestCase):
    def test_build_is_byte_identical_each_time(self):
        self.assertEqual(generator.build_pack(), generator.build_pack())

    def test_matches_the_committed_expected_summary(self):
        committed = json.loads((EXAMPLES / 'expected_intake.json').read_text(encoding='utf-8'))
        self.assertEqual(generator.expected_summary(), committed)

    def test_two_generated_folders_match_and_match_their_hashes(self):
        expected = {item['path']: item for item in generator.expected_summary()['files']}
        with tempfile.TemporaryDirectory() as first, tempfile.TemporaryDirectory() as second:
            generator.write_pack(first)
            generator.write_pack(second)
            for path, item in expected.items():
                one = (Path(first) / path).read_bytes()
                self.assertEqual(one, (Path(second) / path).read_bytes())
                self.assertEqual(hashlib.sha256(one).hexdigest(), item['sha256'])
                self.assertEqual(len(one), item['size_bytes'])

    def test_pack_digest_covers_every_path_and_hash(self):
        files = dict(generator.build_pack())
        before = generator.pack_digest(files)
        path = sorted(files)[0]
        files[path] += b'x'
        self.assertNotEqual(before, generator.pack_digest(files))


class Contents(unittest.TestCase):
    def setUp(self):
        self.files = generator.build_pack()

    def test_includes_each_required_kind(self):
        suffixes = {Path(path).suffix for path in self.files}
        self.assertLessEqual({'.md', '.json', '.csv', '.txt', '.zip'}, suffixes)

    def test_pack_stays_small(self):
        self.assertLess(sum(map(len, self.files.values())), 16 * 1024)

    def test_every_supported_file_inspects_cleanly(self):
        for path, data in self.files.items():
            with self.subTest(path=path):
                if path.endswith('.zip'):
                    result = inspect_archive(data, path)
                elif path.endswith('.tga'):
                    continue
                else:
                    result = inspect_text(data, path)
                self.assertEqual(result['status'], 'ok')

    def test_zip_has_fixed_timestamps_and_valid_stored_payloads(self):
        with zipfile.ZipFile(io.BytesIO(self.files['archive/old-drafts.zip'])) as archive:
            self.assertIsNone(archive.testzip())
            self.assertEqual({info.date_time for info in archive.infolist()}, {generator.ZIP_TIMESTAMP})
            self.assertEqual({info.compress_type for info in archive.infolist()}, {zipfile.ZIP_STORED})

    def test_tga_is_well_formed_without_using_the_core_decoder(self):
        data = self.files['textures/ember.tga']
        header = struct.unpack_from('<BBBHHBHHHHBB', data)
        self.assertEqual((header[2], header[8], header[9], header[10]), (2, 2, 2, 24))
        self.assertEqual(len(data), 18 + 2 * 2 * 3)

    def test_adversarial_line_is_inert_source_text(self):
        result = inspect_text(self.files['notes/session-log.txt'], 'session-log.txt')
        self.assertIn('Ignore previous instructions', result['facts']['excerpt'])


class Refusals(unittest.TestCase):
    def test_refuses_nonempty_directory_and_changes_nothing(self):
        with tempfile.TemporaryDirectory() as root:
            keep = Path(root) / 'keep.txt'
            keep.write_bytes(b'precious')
            with self.assertRaises(generator.PackError):
                generator.write_pack(root)
            self.assertEqual(tree(root), ['keep.txt'])
            self.assertEqual(keep.read_bytes(), b'precious')

    def test_refuses_a_file_as_output(self):
        with tempfile.TemporaryDirectory() as root:
            target = Path(root) / 'file'
            target.write_bytes(b'x')
            with self.assertRaises(generator.PackError):
                generator.write_pack(target)
            self.assertEqual(target.read_bytes(), b'x')

    def test_refuses_a_symlinked_output(self):
        with tempfile.TemporaryDirectory() as root:
            real, link = Path(root) / 'real', Path(root) / 'link'
            real.mkdir()
            try:
                link.symlink_to(real, target_is_directory=True)
            except OSError:
                self.skipTest('symlinks unavailable to this user')
            with self.assertRaises(generator.PackError):
                generator.write_pack(link)
            self.assertEqual(tree(real), [])

    def test_accepts_an_empty_or_new_directory(self):
        with tempfile.TemporaryDirectory() as root:
            generator.write_pack(root)
            self.assertIn('notes/README.md', tree(root))
        with tempfile.TemporaryDirectory() as root:
            nested = Path(root) / 'new' / 'pack'
            generator.write_pack(nested)
            self.assertIn('notes/README.md', tree(nested))

    def test_writes_nothing_outside_the_selected_output(self):
        with tempfile.TemporaryDirectory() as root:
            output = Path(root) / 'pack'
            generator.write_pack(output)
            self.assertEqual({p.name for p in Path(root).iterdir()}, {'pack'})
            for path in tree(output):
                self.assertTrue((output / path).resolve().is_relative_to(output.resolve()))

    def test_escaping_pack_path_is_refused_before_writing(self):
        for bad in ('../escape.txt', '/abs.txt', 'C:/abs.txt', 'a\\..\\b.txt', ''):
            with self.subTest(bad=bad), tempfile.TemporaryDirectory() as root:
                output = Path(root) / 'pack'
                with self.assertRaises(generator.PackError):
                    generator.write_pack(output, {'good.txt': b'x', bad: b'y'})
                self.assertFalse(output.exists())


class CommandLine(unittest.TestCase):
    def run_main(self, *argv):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            code = generator.main(list(argv))
        return code, out.getvalue(), err.getvalue()

    def test_generates_and_reports(self):
        with tempfile.TemporaryDirectory() as root:
            code, out, _ = self.run_main(root)
            self.assertEqual(code, 0)
            self.assertIn(generator.expected_summary()['pack_sha256'], out)

    def test_refusal_exits_nonzero_with_a_message(self):
        with tempfile.TemporaryDirectory() as root:
            (Path(root) / 'x').write_bytes(b'x')
            code, _, err = self.run_main(root)
            self.assertEqual(code, 2)
            self.assertIn('not empty', err)

    def test_print_expected_writes_nothing(self):
        before = tree(EXAMPLES)
        code, out, _ = self.run_main('--print-expected')
        self.assertEqual(code, 0)
        self.assertEqual(json.loads(out), generator.expected_summary())
        self.assertEqual(tree(EXAMPLES), before)


class ScriptSafety(unittest.TestCase):
    def test_no_network_subprocess_or_execution(self):
        tree_ = ast.parse(SCRIPT.read_text(encoding='utf-8'))
        for node in ast.walk(tree_):
            if isinstance(node, ast.Import):
                names = {alias.name.split('.')[0] for alias in node.names}
            elif isinstance(node, ast.ImportFrom):
                names = {(node.module or '').split('.')[0]}
            else:
                self.assertFalse(isinstance(node, ast.Name) and node.id in {'eval', 'exec', '__import__'})
                continue
            self.assertFalse(names & {'socket', 'urllib', 'http', 'subprocess', 'ftplib', 'requests', 'shutil', 'random', 'time'})

    def test_no_machine_specific_paths_in_library_or_example(self):
        roots = [HERE.parents[1] / 'rekindra_intake', EXAMPLES]
        for root in roots:
            for path in root.glob('*.py'):
                text = path.read_text(encoding='utf-8')
                self.assertNotRegex(text, r'\b[A-Za-z]:[\\/]{1,2}[A-Za-z]', path)
                self.assertNotIn(os.path.expanduser('~'), text)


if __name__ == '__main__':
    unittest.main()
