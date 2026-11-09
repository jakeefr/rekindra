"""Common image formats recover to PNG in a child process; damaged ones never gain pixels."""
import hashlib
import io
from pathlib import Path
import random
import tempfile
import unittest
from unittest import mock

try:
    from PIL import Image
except ImportError:
    Image = None

from rekindra_core import image_recovery
from rekindra_core.compositions import CompositionStore
from rekindra_core.identify import identify
from rekindra_core.image_recovery import ImageRefused, read_image
from rekindra_core.projects import ImageRefusal, ProjectStore

SIZE = (64, 48)
LOSSLESS = {'png', 'bmp', 'tiff', 'pcx', 'ppm', 'qoi', 'sgi', 'webp', 'dds'}
# tag: (file extension, Pillow writer, save options)
FORMATS = {
    'png': ('png', 'PNG', {}),
    'jpeg': ('jpg', 'JPEG', {'quality': 90}),
    'bmp': ('bmp', 'BMP', {}),
    'gif': ('gif', 'GIF', {}),
    'tiff': ('tif', 'TIFF', {}),
    'pcx': ('pcx', 'PCX', {}),
    'ico': ('ico', 'ICO', {'sizes': [(48, 48)]}),
    'webp': ('webp', 'WEBP', {'lossless': True}),
    'ppm': ('ppm', 'PPM', {}),
    'qoi': ('qoi', 'QOI', {}),
    'sgi': ('sgi', 'SGI', {}),
    'dds': ('dds', 'DDS', {}),
}


def noise(size=SIZE, seed=7):
    return Image.frombytes('RGB', size, random.Random(seed).randbytes(size[0] * size[1] * 3))


def smooth(size):
    """Compressible and detailed enough to survive JPEG, with no flat gray region."""
    width, height = size
    data = bytearray()
    for y in range(height):
        for x in range(width):
            data += bytes((x * 255 // max(width - 1, 1), y * 255 // max(height - 1, 1), (x + y) * 7 % 256))
    return Image.frombytes('RGB', size, bytes(data))


def encoded(image, writer, **options):
    buffer = io.BytesIO()
    image.save(buffer, writer, **options)
    return buffer.getvalue()


def decode(png):
    image = Image.open(io.BytesIO(png))
    image.load()
    return image


@unittest.skipIf(Image is None, 'Pillow is not installed, so the image reader cannot run')
class ReadImageTests(unittest.TestCase):
    def test_each_format_identifies_and_recovers(self):
        Image.init()
        tried = 0
        for tag, (extension, writer, options) in FORMATS.items():
            if writer not in Image.SAVE:
                continue    # older Pillow cannot write this fixture
            with self.subTest(format=tag):
                tried += 1
                source = noise((48, 48) if tag == 'ico' else SIZE)
                data = encoded(source, writer, **options)
                self.assertEqual(identify(data[:65536], 'old.' + extension), tag)
                self.assertEqual(identify(data[:65536], 'no_extension'), tag if tag != 'ppm' else tag)
                result = read_image(data, tag)
                header = result['header']
                self.assertEqual((header['width'], header['height']), source.size)
                self.assertEqual(header['source_format'], tag)
                self.assertIs(header['partial'], False)
                self.assertEqual(header['decoded_fraction'], 1.0)
                recovered = decode(result['full'])
                self.assertEqual(recovered.format, 'PNG')
                self.assertEqual(recovered.size, source.size)
                if tag in LOSSLESS:
                    self.assertEqual(recovered.convert('RGB').tobytes(), source.tobytes())
        self.assertGreaterEqual(tried, 11)

    def test_truncated_png_keeps_only_real_rows(self):
        full = noise((80, 80))
        data = encoded(full, 'PNG')
        result = read_image(data[:len(data) * 6 // 10], 'png')
        header = result['header']
        self.assertIs(header['partial'], True)
        self.assertTrue(0 < header['decoded_fraction'] < 1)
        self.assertEqual((header['original_width'], header['original_height']), (80, 80))
        recovered = decode(result['full'])
        self.assertLess(recovered.size[1], 80)
        self.assertGreater(recovered.size[1], 20)
        self._assert_shown_pixels_match(recovered, full, tolerance=0)
        self.assertIn('nothing was filled in', ' '.join(header['warnings']))

    def test_truncated_jpeg_gains_no_gray_rows(self):
        full = smooth((256, 256))
        data = encoded(full, 'JPEG', quality=95, progressive=False)
        result = read_image(data[:len(data) // 2], 'jpeg')
        header = result['header']
        self.assertIs(header['partial'], True)
        self.assertTrue(0 < header['decoded_fraction'] < 1)
        recovered = decode(result['full'])
        self.assertLess(recovered.size[1], 256)
        self._assert_shown_pixels_match(recovered, decode(encoded_to_png(data)), tolerance=2, skip_bottom=16)

    def _assert_shown_pixels_match(self, recovered, reference, tolerance, skip_bottom=0):
        width, height = recovered.size
        rgba = recovered.convert('RGBA').tobytes()
        truth = reference.convert('RGB').tobytes()
        full_width = reference.size[0]
        shown = 0
        for y in range(height - skip_bottom):
            for x in range(width):
                alpha_at = (y * width + x) * 4
                if rgba[alpha_at + 3] == 0:
                    continue
                shown += 1
                at = (y * full_width + x) * 3
                for channel in range(3):
                    self.assertLessEqual(abs(rgba[alpha_at + channel] - truth[at + channel]), tolerance, (x, y, channel))
        self.assertGreater(shown, 0)

    def test_not_an_image_is_refused(self):
        with self.assertRaises(ImageRefused) as caught:
            read_image(b'\x89PNG\r\n\x1a\n' + bytes(range(256)) * 4, 'png')
        self.assertEqual(caught.exception.code, 'damaged_image')

    def test_header_only_jpeg_is_refused_not_gray(self):
        data = encoded(noise((64, 64)), 'JPEG')
        scan = data.index(b'\xff\xda')
        with self.assertRaises(ImageRefused) as caught:
            read_image(data[:scan + 2], 'jpeg')
        self.assertEqual(caught.exception.code, 'damaged_image')

    def test_exif_date_and_orientation(self):
        exif = Image.Exif()
        exif[0x0112] = 6
        exif.get_ifd(0x8769)[36867] = '2004:07:01 12:30:00'
        header_image = noise((60, 30))
        result = read_image(encoded(header_image, 'JPEG', exif=exif), 'jpeg')
        header = result['header']
        self.assertEqual(header['exif_date'], '2004:07:01 12:30:00')
        self.assertEqual(header['exif_date_tag'], 'DateTimeOriginal')
        self.assertEqual(header['exif_orientation'], 6)
        self.assertEqual((header['width'], header['height']), (30, 60))

    def test_tiff_orientation_is_applied_once(self):
        source = noise((60, 30))
        result = read_image(encoded(source, 'TIFF', tiffinfo={0x0112: 6}), 'tiff')
        self.assertEqual(result['header']['exif_orientation'], 6)
        recovered = decode(result['full'])
        self.assertEqual(recovered.size, (30, 60))
        self.assertEqual(recovered.convert('RGB').tobytes(), source.transpose(Image.Transpose.ROTATE_270).tobytes())

    def test_truncated_rotated_tiff_recovers_its_real_pixels(self):
        source = noise((300, 100))
        data = encoded(source, 'TIFF', tiffinfo={0x0112: 6})
        result = read_image(data[:len(data) * 6 // 10], 'tiff')
        header = result['header']
        self.assertIs(header['partial'], True)
        self.assertTrue(0 < header['decoded_fraction'] < 1, header['decoded_fraction'])
        self.assertEqual((header['original_width'], header['original_height']), (100, 300))
        recovered = decode(result['full'])
        self.assertLess(recovered.size[0], 100)
        self.assertEqual(recovered.size[1], 300)
        turned = source.transpose(Image.Transpose.ROTATE_270)
        reference = turned.crop((100 - recovered.size[0], 0, 100, 300))
        self._assert_shown_pixels_match(recovered, reference, tolerance=0)

    def test_truncated_transparent_gif_counts_only_real_pixels(self):
        full = noise((80, 80)).quantize(255)
        data = encoded(full, 'GIF', transparency=0)
        reference = decode(encoded(Image.open(io.BytesIO(data)), 'PNG'))
        result = read_image(data[:len(data) * 6 // 10], 'gif')
        header = result['header']
        self.assertIs(header['partial'], True)
        self.assertTrue(0 < header['decoded_fraction'] < 1, header['decoded_fraction'])
        recovered = decode(result['full'])
        self.assertLess(recovered.size[1], 80)
        self._assert_shown_pixels_match(recovered, reference, tolerance=0)

    def test_absent_exif_stays_null(self):
        self.assertIsNone(read_image(encoded(noise(), 'JPEG'), 'jpeg')['header']['exif_date'])

    def test_animated_gif_says_first_frame_only(self):
        frames = [noise((32, 32), seed) for seed in (1, 2, 3)]
        data = encoded(frames[0], 'GIF', save_all=True, append_images=frames[1:], duration=100)
        header = read_image(data, 'gif')['header']
        self.assertIs(header['multi_frame'], True)
        self.assertIn('first', ' '.join(header['warnings']))

    def test_sixteen_bit_png_keeps_its_depth(self):
        image = Image.new('I;16', (8, 8), 40000)
        recovered = decode(read_image(encoded(image, 'PNG'), 'png')['full'])
        self.assertTrue(recovered.mode.startswith('I'))
        self.assertEqual(recovered.getpixel((3, 3)), 40000)

    def test_pixel_cap_refuses_before_decoding(self):
        with self.assertRaises(ImageRefused) as caught:
            read_image(encoded(Image.new('L', (5000, 5000)), 'PNG'), 'png')
        self.assertEqual(caught.exception.code, 'image_too_large')

    def test_scene_copy_fits_the_budget_and_leaves_the_recovery_whole(self):
        data = encoded(noise((1400, 1400)), 'PNG', compress_level=1)
        result = read_image(data, 'png')
        self.assertIsNotNone(result['scene'])
        self.assertLessEqual(len(result['scene']), image_recovery.SCENE_BYTES)
        self.assertEqual(decode(result['full']).size, (1400, 1400))
        self.assertLess(decode(result['scene']).size[0], 1400)

    def test_missing_reader_is_named(self):
        with mock.patch.object(image_recovery, '_reader_dir', return_value=None):
            with self.assertRaises(ImageRefused) as caught:
                read_image(encoded(noise(), 'PNG'), 'png')
        self.assertEqual(caught.exception.code, 'image_reader_unavailable')

    def test_oversized_input_is_refused_unread(self):
        with self.assertRaises(ImageRefused) as caught:
            read_image(b'\0' * (image_recovery.MAX_IMAGE_BYTES + 1), 'png')
        self.assertEqual(caught.exception.code, 'image_too_large')


def encoded_to_png(jpeg_bytes):
    return encoded(Image.open(io.BytesIO(jpeg_bytes)), 'PNG')


class IdentifyStructureTests(unittest.TestCase):
    def test_short_magics_do_not_claim_other_files(self):
        self.assertEqual(identify(b'BM is how these notes begin, and they go on for a while.', 'notes.txt'), 'text')
        self.assertEqual(identify(b'P6 2 2 255 is a sentence here', 'notes.txt'), 'text')
        self.assertEqual(identify(b'\n\x05 hello', 'a.bin'), 'unknown')

    def test_plain_text_ppm_needs_the_extension(self):
        self.assertEqual(identify(b'P6 2 2 255\nabcdefghijkl', 'x.ppm'), 'ppm')


@unittest.skipIf(Image is None, 'Pillow is not installed, so the image reader cannot run')
class StoreTests(unittest.TestCase):
    def setUp(self):
        base = Path(__file__).resolve().parents[1] / '.local' / 'tests'
        base.mkdir(parents=True, exist_ok=True)
        temp = tempfile.TemporaryDirectory(dir=base)
        self.addCleanup(temp.cleanup)
        self.base = Path(temp.name)
        self.source = self.base / 'source'
        self.source.mkdir()
        self.store = ProjectStore(self.base / 'store')

    def inspect(self, name, data):
        (self.source / name).write_bytes(data)
        project = self.store.inspect(self.source)
        return project, project['assets'][0]

    def test_recovery_records_provenance_and_leaves_the_source(self):
        data = encoded(noise(), 'BMP')
        project, asset = self.inspect('old.bmp', data)
        artifact = self.store.recover(project['project_id'], asset['asset_id'])
        self.assertEqual((self.source / 'old.bmp').read_bytes(), data)
        self.assertEqual(asset['format'], 'bmp')
        self.assertEqual((artifact['kind'], artifact['format']), ('recovered', 'png'))
        self.assertEqual(artifact['source_sha256'], hashlib.sha256(data).hexdigest())
        self.assertEqual(artifact['source_format'], 'bmp')
        self.assertTrue(artifact['decoder'].startswith('pillow-'))
        png = Path(artifact['path']).read_bytes()
        self.assertEqual(hashlib.sha256(png).hexdigest(), artifact['sha256'])
        self.assertEqual(self.store.status(project['project_id'])['artifacts'][0]['asset_id'], asset['asset_id'])

    def test_refusal_carries_its_code(self):
        project, asset = self.inspect('bad.png', b'\x89PNG\r\n\x1a\n' + bytes(range(256)) * 4)
        with self.assertRaises(ImageRefusal) as caught:
            self.store.recover(project['project_id'], asset['asset_id'])
        self.assertEqual(caught.exception.code, 'damaged_image')

    def test_scene_source_for_a_whole_png_stays_original(self):
        data = encoded(noise(), 'PNG')
        project, asset = self.inspect('whole.png', data)
        source = CompositionStore(self.store).sources(project['project_id'], [asset['asset_id']])[0]
        self.assertEqual((source['kind'], source['mime_type'], source['data']), ('original', 'image/png', data))

    def test_scene_source_for_a_truncated_jpeg_is_the_recovered_copy(self):
        data = encoded(smooth((256, 256)), 'JPEG', quality=95)
        project, asset = self.inspect('cut.jpg', data[:len(data) // 2])
        source = CompositionStore(self.store).sources(project['project_id'], [asset['asset_id']])[0]
        self.assertEqual((source['kind'], source['mime_type']), ('recovered', 'image/png'))
        self.assertLess(decode(source['data']).size[1], 256)

    def test_scene_source_for_bmp_is_recovered_png(self):
        project, asset = self.inspect('old.bmp', encoded(noise(), 'BMP'))
        source = CompositionStore(self.store).sources(project['project_id'], [asset['asset_id']])[0]
        self.assertEqual((source['kind'], source['mime_type']), ('recovered', 'image/png'))


if __name__ == '__main__':
    unittest.main()
