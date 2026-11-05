import struct
import unittest
import zlib

from rekindra_core.tga import decode_tga, RecoveryError
from rekindra_core.png import encode_png


def fixture(pixels=b'\x00\x00\xff', width=1, height=1, depth=24, descriptor=32, kind=2, cmap=0):
    return struct.pack('<BBBHHBHHHHBB', 0, cmap, kind, 0, 0, 0, 0, 0,
                       width, height, depth, descriptor) + pixels


class TgaTests(unittest.TestCase):
    def test_bgr_is_converted_to_red_rgba(self):
        image = decode_tga(fixture())
        self.assertEqual((image.width, image.height), (1, 1))
        self.assertEqual(image.rgba, b'\xff\x00\x00\xff')

    def test_all_origins_produce_top_left_row_major_pixels(self):
        # Canonical two-by-two image: red, green / blue, white.
        colors = [b'\x00\x00\xff', b'\x00\xff\x00', b'\xff\x00\x00', b'\xff\xff\xff']
        cases = [(32, [0, 1, 2, 3]), (0, [2, 3, 0, 1]),
                 (48, [1, 0, 3, 2]), (16, [3, 2, 1, 0])]
        for descriptor, order in cases:
            with self.subTest(descriptor=descriptor):
                image = decode_tga(fixture(b''.join(colors[i] for i in order), 2, 2, descriptor=descriptor))
                self.assertEqual(image.rgba, bytes.fromhex('ff0000ff00ff00ff0000ffffffffffff'))

    def test_preserves_declared_alpha(self):
        image = decode_tga(fixture(b'\x03\x02\x01\x40', depth=32, descriptor=40))
        self.assertEqual(image.rgba, b'\x01\x02\x03\x40')

    def test_undeclared_attribute_bytes_are_not_transparency(self):
        image = decode_tga(fixture(b'\x03\x02\x01\x00', depth=32))
        self.assertEqual(image.rgba, b'\x01\x02\x03\xff')

    def test_rle_and_raw_packets(self):
        image = decode_tga(fixture(b'\x81\x00\x00\xff\x00\x00\xff\x00', 3, kind=10))
        self.assertEqual(image.rgba, bytes.fromhex('ff0000ffff0000ff00ff00ff'))

    def test_rejects_invalid_or_unsupported_data(self):
        cases = [b'', fixture()[:-1], fixture(width=0), fixture(width=65535, height=65535),
                 fixture(cmap=1), fixture(depth=16), fixture(descriptor=96),
                 fixture(descriptor=33), fixture(kind=3),
                 fixture(b'\x82\x00\x00\xff', width=2, kind=10),
                 fixture(b'\x80\x00', kind=10)]
        for data in cases:
            with self.subTest(data=data[:18]):
                with self.assertRaises(RecoveryError):
                    decode_tga(data)

    def test_enforces_custom_pixel_limit(self):
        with self.assertRaises(RecoveryError):
            decode_tga(fixture(b'\0' * 12, 2, 2), max_pixels=3)

    def test_png_pixels_and_crc_are_valid(self):
        png = encode_png(decode_tga(fixture()))
        self.assertEqual(png[:8], b'\x89PNG\r\n\x1a\n')
        cursor, compressed, kinds = 8, b'', []
        while cursor < len(png):
            size = struct.unpack('>I', png[cursor:cursor+4])[0]
            kind = png[cursor+4:cursor+8]
            payload = png[cursor+8:cursor+8+size]
            crc = struct.unpack('>I', png[cursor+8+size:cursor+12+size])[0]
            self.assertEqual(crc, zlib.crc32(kind+payload) & 0xffffffff)
            if kind == b'IHDR':
                self.assertEqual(struct.unpack('>IIBBBBB', payload), (1, 1, 8, 6, 0, 0, 0))
            if kind == b'IDAT':
                compressed += payload
            kinds.append(kind)
            cursor += 12+size
        self.assertEqual(kinds, [b'IHDR', b'IDAT', b'IEND'])
        self.assertEqual(zlib.decompress(compressed), b'\0\xff\0\0\xff')


if __name__ == '__main__':
    unittest.main()
