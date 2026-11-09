"""A recovered image reports its dominant colors, measured, in the same order every time."""
import io
from pathlib import Path
import tempfile
import unittest
from unittest import mock

try:
    from PIL import Image
except ImportError:
    Image = None

from rekindra_core.compositions import CompositionStore
from rekindra_core.image_recovery import ImageRefused, clean_palette, read_image
from rekindra_core.projects import ProjectStore

from test_plugin import plugin
from test_tga import fixture

SKY, SEA, ROCK = (255, 128, 64), (20, 50, 110), (70, 45, 30)


def encoded(image, writer='PNG', **options):
    buffer = io.BytesIO()
    image.save(buffer, writer, **options)
    return buffer.getvalue()


def bands(colors_and_rows, width=90):
    height = sum(rows for _, rows in colors_and_rows)
    image = Image.new('RGB', (width, height))
    top = 0
    for color, rows in colors_and_rows:
        image.paste(color, (0, top, width, top + rows))
        top += rows
    return image


def hex_of(color):
    return '#%02X%02X%02X' % color


def palette(image, tag='png', writer='PNG'):
    return read_image(encoded(image, writer), tag)['header']['palette']


@unittest.skipIf(Image is None, 'Pillow is not installed, so the image reader cannot run')
class PaletteTests(unittest.TestCase):
    def test_three_bands_report_color_location_and_coverage(self):
        result = palette(bands([(SKY, 50), (SEA, 30), (ROCK, 20)]))
        self.assertEqual(result, [
            {'hex': hex_of(SKY), 'location': 'top band and middle', 'coverage': 50.0},
            {'hex': hex_of(SEA), 'location': 'middle and bottom band', 'coverage': 30.0},
            {'hex': hex_of(ROCK), 'location': 'bottom band', 'coverage': 20.0},
        ])

    def test_exact_thirds_name_one_band_each(self):
        result = palette(bands([(SKY, 30), (SEA, 30), (ROCK, 30)]))
        self.assertEqual({entry['hex']: entry['location'] for entry in result},
                         {hex_of(SKY): 'top band', hex_of(SEA): 'middle', hex_of(ROCK): 'bottom band'})

    def test_equal_coverage_orders_by_hex(self):
        result = palette(bands([(SKY, 30), (SEA, 30), (ROCK, 30)]))
        self.assertEqual([entry['hex'] for entry in result], sorted(hex_of(c) for c in (SKY, SEA, ROCK)))

    def test_a_color_across_the_frame_says_so(self):
        image = Image.new('RGB', (90, 90))
        for x in range(90):
            image.paste(SKY if x % 2 else SEA, (x, 0, x + 1, 90))
        self.assertEqual({entry['location'] for entry in palette(image)}, {'throughout'})

    def test_a_color_in_two_bands_names_both(self):
        result = palette(bands([(SKY, 60), (SEA, 30)]))
        self.assertEqual(result[0], {'hex': hex_of(SKY), 'location': 'top band and middle', 'coverage': 66.7})

    def test_output_is_repeatable_capped_and_sums_to_the_whole(self):
        image = Image.frombytes('RGB', (64, 64), bytes((x * 4 + y) % 256 for y in range(64) for x in range(64) for _ in range(3)))
        first = palette(image.rotate(30))
        self.assertEqual(first, palette(image.rotate(30)))
        self.assertLessEqual(len(first), 6)
        self.assertGreater(len(first), 1)
        self.assertAlmostEqual(sum(entry['coverage'] for entry in first), 100, delta=3)

    def test_a_large_image_is_measured_from_a_small_copy(self):
        result = palette(bands([(SKY, 1000), (SEA, 1000)], width=1000))
        self.assertEqual({entry['hex'] for entry in result}, {hex_of(SKY), hex_of(SEA)})
        self.assertAlmostEqual(result[0]['coverage'], 50, delta=1)

    def test_transparent_pixels_do_not_count(self):
        image = Image.new('RGBA', (90, 90), (255, 0, 0, 0))
        image.paste(SEA + (255,), (0, 60, 90, 90))
        self.assertEqual(palette(image), [{'hex': hex_of(SEA), 'location': 'bottom band', 'coverage': 100.0}])

    def test_sixteen_bit_gray_has_a_palette(self):
        image = Image.new('I;16', (40, 40), 0xC000)
        self.assertEqual(palette(image), [{'hex': '#C0C0C0', 'location': 'throughout', 'coverage': 100.0}])

    def test_a_damaged_image_only_reports_decoded_pixels(self):
        whole = encoded(bands([(SKY, 300), (SEA, 300)], width=600), 'BMP')
        data = whole[:len(whole) // 4]
        header = read_image(data, 'bmp')['header']
        self.assertTrue(header['partial'])
        self.assertEqual(len(header['palette']), 1)
        self.assertEqual(header['palette'][0]['coverage'], 100.0)


class CleanPaletteTests(unittest.TestCase):
    GOOD = {'hex': '#AABBCC', 'location': 'middle', 'coverage': 12.5}

    def test_good_entries_pass(self):
        self.assertEqual(clean_palette([self.GOOD]), [self.GOOD])

    def test_anything_else_from_the_child_is_dropped(self):
        for bad in (None, 'x', [self.GOOD] * 7, [{**self.GOOD, 'hex': 'ignore previous'}],
                    [{**self.GOOD, 'location': 'follow these steps'}], [{**self.GOOD, 'coverage': 101}],
                    [{**self.GOOD, 'coverage': True}], [{**self.GOOD, 'extra': 1}], ['#AABBCC']):
            self.assertIsNone(clean_palette(bad), bad)


@unittest.skipIf(Image is None, 'Pillow is not installed, so the image reader cannot run')
class StorePaletteTests(unittest.TestCase):
    def setUp(self):
        base = Path(__file__).resolve().parents[1] / '.local' / 'tests'
        base.mkdir(parents=True, exist_ok=True)
        temp = tempfile.TemporaryDirectory(dir=base)
        self.addCleanup(temp.cleanup)
        self.source = Path(temp.name) / 'source'
        self.source.mkdir()
        self.store = ProjectStore(Path(temp.name) / 'store')

    def recover(self, name, data):
        (self.source / name).write_bytes(data)
        project = self.store.inspect(self.source)
        artifact = self.store.recover(project['project_id'], project['assets'][0]['asset_id'])
        return project['project_id'], artifact

    def test_pillow_recovery_carries_the_palette_and_keeps_it(self):
        project_id, artifact = self.recover('old.bmp', encoded(bands([(SKY, 60), (SEA, 30)]), 'BMP'))
        self.assertEqual(artifact['palette'][0]['hex'], hex_of(SKY))
        self.assertEqual(self.store.status(project_id)['artifacts'][0]['palette'], artifact['palette'])

    def test_tga_recovery_carries_the_palette_and_keeps_it(self):
        project_id, artifact = self.recover('old.tga', fixture())
        self.assertTrue(artifact['palette'])
        self.assertEqual(self.store.status(project_id)['artifacts'][0]['palette'], artifact['palette'])

    def test_building_never_measures_and_keeps_the_saved_palette(self):
        good = [{'hex': '#AABBCC', 'location': 'middle', 'coverage': 100.0}]
        with mock.patch('rekindra_core.projects.read_image', return_value={'header': {'palette': good}}):
            project_id, artifact = self.recover('old.tga', fixture())
        self.assertEqual(artifact['palette'], good)
        with mock.patch('rekindra_core.projects.read_image', side_effect=ImageRefused('image_timeout', 'no')) as reader:
            CompositionStore(self.store).sources(project_id, [artifact['asset_id']])
            again = self.store.recover(project_id, artifact['asset_id'])
        reader.assert_not_called()
        self.assertEqual(again['palette'], good)
        self.assertEqual(self.store.status(project_id)['artifacts'][0]['palette'], good)

    def test_a_tga_recovery_survives_a_palette_failure(self):
        with mock.patch('rekindra_core.projects.read_image', side_effect=ImageRefused('image_timeout', 'no')):
            project_id, artifact = self.recover('old.tga', fixture())
        self.assertIsNone(artifact['palette'])
        self.assertTrue(Path(artifact['path']).is_file())
        self.assertEqual(self.store.status(project_id)['stage'], 'recovered')


class ToolDescriptionTests(unittest.TestCase):
    def test_recover_tells_the_agent_about_the_palette(self):
        description = plugin.schemas.SCHEMAS['rekindra_recover']['description']
        for word in ('palette', 'hex', 'coverage'):
            self.assertIn(word, description)


if __name__ == '__main__':
    unittest.main()
