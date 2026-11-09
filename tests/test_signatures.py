import os
from pathlib import Path
import struct
import tempfile
import unittest

from rekindra_core.identify import identify
from rekindra_core.projects import ProjectError, ProjectStore
from rekindra_core.signatures import file_kind, identification

# Synthetic headers only: each is the documented opening of its format, then filler.
TAIL = bytes(range(128, 228))
PE = b'MZ' + bytes(58) + struct.pack('<I', 128) + bytes(64) + b'PE\0\0' + TAIL


def ftyp(brand, *compatible):
    body = b'ftyp' + brand + bytes(4) + b''.join(compatible)
    return struct.pack('>I', len(body) + 4) + body + TAIL


CASES = {
    'RAR archive': b'Rar!\x1a\x07\x01\x00' + TAIL,
    '7-Zip archive': b"7z\xbc\xaf'\x1c" + TAIL,
    'gzip archive': b'\x1f\x8b\x08' + TAIL,
    'bzip2 archive': b'BZh91AY&SY' + TAIL,
    'xz archive': b'\xfd7zXZ\0' + TAIL,
    'Zstandard archive': b'\x28\xb5\x2f\xfd' + TAIL,
    'TAR archive': bytes(257) + b'ustar\x0000' + TAIL,
    'ISO disc image': bytes(32769) + b'CD001' + TAIL,
    'Windows cabinet archive': b'MSCF\0\0\0\0' + TAIL,
    'Microsoft compound file (legacy Office document or Thumbs.db)': b'\xd0\xcf\x11\xe0\xa1\xb1\x1a\xe1' + TAIL,
    'SQLite database': b'SQLite format 3\0' + TAIL,
    'WordPerfect document': b'\xffWPC' + TAIL,
    'Windows shortcut': b'L\0\0\0\x01\x14\x02\0' + TAIL,
    'Windows executable': PE,
    'ELF executable': b'\x7fELF\x02\x01' + TAIL,
    'macOS executable': b'\xcf\xfa\xed\xfe' + TAIL,
    'WebAssembly module': b'\0asm\x01\0\0\0' + TAIL,
    'Photoshop document': b'8BPS\0\x01' + TAIL,
    'JPEG 2000 image': b'\0\0\0\x0cjP  \r\n\x87\n' + TAIL,
    'HEIC/HEIF image': ftyp(b'heic'),
    'AVIF image': ftyp(b'mif1', b'avif'),
    'QuickTime video': ftyp(b'qt  '),
    'M4A audio': ftyp(b'M4A '),
    'MP4 video': ftyp(b'isom'),
    'WebM video': b'\x1a\x45\xdf\xa3\x9fB\x82\x84webm' + TAIL,
    'Matroska video': b'\x1a\x45\xdf\xa3\x9fB\x82\x88matroska' + TAIL,
    'AVI video': b'RIFF\x10\0\0\0AVI ' + TAIL,
    'WAV audio': b'RIFF\x10\0\0\0WAVE' + TAIL,
    'MP3 audio': b'ID3\x04\0\0\0\0\0\x10' + TAIL,
    'FLAC audio': b'fLaC\0\0\0\x22' + TAIL,
    'Ogg media': b'OggS\0\x02' + TAIL,
    'MIDI audio': b'MThd\0\0\0\x06' + TAIL,
}


class FileKindTests(unittest.TestCase):
    def test_every_named_signature(self):
        for label, data in CASES.items():
            with self.subTest(label):
                self.assertEqual(file_kind(data), label)

    def test_each_case_still_reaches_the_unknown_route(self):
        # A signature name must never change what the supported-format router decides.
        for label, data in CASES.items():
            with self.subTest(label):
                self.assertEqual(identify(data[:65536], 'no_extension'), 'unknown')

    def test_short_lookalikes_are_not_claimed(self):
        for data in (b'MZ' + bytes(200), b'MZ', b'', b'RIFF\x10\0\0\0ABCD' + TAIL, b'ftyp', b'\xffWP', bytes(600),
                     PE[:100], os.urandom(0) + b'\x89\x00\x01\x02' + TAIL):
            with self.subTest(data[:12]):
                self.assertIsNone(file_kind(data))

    def test_ftyp_brands_are_not_all_mp4(self):
        self.assertEqual(file_kind(ftyp(b'crx ')), 'Canon CR3 raw image')
        self.assertEqual(file_kind(ftyp(b'M4P ')), 'M4A audio')
        self.assertEqual(file_kind(ftyp(b'3gp5')), 'MP4 video')
        self.assertEqual(file_kind(ftyp(b'zzzz')), 'ISO media file')

    def test_ftyp_box_size_must_fit(self):
        for size in (8, 15, 100000):
            with self.subTest(size):
                self.assertIsNone(file_kind(struct.pack('>I', size) + b'ftypisom' + bytes(4) + TAIL))

    def test_pe_pointer_outside_header_is_handled(self):
        far = b'MZ' + bytes(58) + struct.pack('<I', 0xFFFFFFFF) + TAIL
        self.assertIsNone(file_kind(far))

    def test_plain_wording(self):
        self.assertEqual(identification(CASES['RAR archive']), 'identified as RAR archive, not supported yet')
        self.assertEqual(identification(b'\x89\x00\x01\x02' + TAIL), 'no known file signature, not supported')


class InspectReportsSignatureTests(unittest.TestCase):
    def setUp(self):
        base = Path(__file__).resolve().parents[1] / '.local' / 'tests'
        base.mkdir(parents=True, exist_ok=True)
        self.temp = tempfile.TemporaryDirectory(dir=base)
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.source = self.base / 'source'
        self.source.mkdir()
        self.store = ProjectStore(self.base / 'store')

    def inspect(self, name, data):
        (self.source / name).write_bytes(data)
        project = self.store.inspect(self.source)
        return project, next(a for a in project['assets'] if a['source_path'] == name)

    def test_extension_does_not_decide_the_name(self):
        data = CASES['RAR archive']
        _, asset = self.inspect('holiday.dat', data)
        self.assertEqual(asset['format'], 'unknown')
        self.assertEqual(asset['identification'], 'identified as RAR archive, not supported yet')
        self.assertEqual((self.source / 'holiday.dat').read_bytes(), data)

    def test_recover_names_what_it_refused(self):
        project, asset = self.inspect('old.bin', CASES['SQLite database'])
        with self.assertRaisesRegex(ProjectError, 'Identified as SQLite database, not supported yet'):
            self.store.recover(project['project_id'], asset['asset_id'])

    def test_no_signature_says_so(self):
        project, asset = self.inspect('blob', b'\x89\x00\x01\x02' + TAIL)
        self.assertEqual(asset['identification'], 'no known file signature, not supported')
        with self.assertRaisesRegex(ProjectError, 'No known file signature, not supported'):
            self.store.recover(project['project_id'], asset['asset_id'])

    def test_supported_files_carry_no_note(self):
        _, asset = self.inspect('note.txt', b'plain words')
        self.assertEqual(asset['format'], 'text')
        self.assertNotIn('identification', asset)

    def test_identification_survives_reload(self):
        project, asset = self.inspect('a.bin', CASES['Windows executable'])
        saved = self.store.status(project['project_id'])['assets'][0]
        self.assertEqual(saved['identification'], asset['identification'])


if __name__ == '__main__':
    unittest.main()
