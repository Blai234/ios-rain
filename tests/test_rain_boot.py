"""Check the Rain boot-v3 packager's stock-header and ramdisk contract."""
import gzip
import struct
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import pack_rain_boot as boot  # noqa: E402


def image(size, offset=0x80000, flags=0xa):
    data = bytearray(size)
    struct.pack_into('<QQQ', data, 8, offset, size, flags)
    data[56:60] = b'ARM\x64'
    return bytes(data)


class RainBootTest(unittest.TestCase):
    def setUp(self):
        self.stock_image = image(8192)
        compressed = gzip.compress(self.stock_image)
        self.ramdisk = b'original ramdisk\0' * 13
        header = bytearray(boot.PAGE)
        header[:8] = b'ANDROID!'
        struct.pack_into('<4I', header, 8, len(compressed), len(self.ramdisk), 0x18000091,
                         boot.V3_HEADER_SIZE)
        struct.pack_into('<I', header, 40, 3)
        header[44:51] = b'console'
        self.stock = (bytes(header) + compressed + bytes(boot.align(len(compressed)) - len(compressed)) +
                      self.ramdisk + bytes(boot.align(len(self.ramdisk)) - len(self.ramdisk)) +
                      bytes(boot.PAGE))
        self.vendor = b'VNDRBOOT' + struct.pack('<II', 3, boot.PAGE) + bytes(boot.PAGE - 16)

    def test_preserves_header_and_ramdisk_and_compresses_image(self):
        shim = image(16384)
        out = boot.pack(self.stock, self.vendor, shim)
        header, ramdisk, extracted = boot.read_stock_boot(out)
        self.assertEqual(header[12:], self.stock[12:boot.PAGE])
        self.assertEqual(ramdisk, self.ramdisk)
        self.assertEqual(extracted, shim)
        self.assertEqual(out[boot.PAGE:boot.PAGE + 2], b'\x1f\x8b')
        self.assertLessEqual(len(out), len(self.stock))

    def test_rejects_mismatched_image_placement(self):
        with self.assertRaisesRegex(ValueError, 'placement'):
            boot.pack(self.stock, self.vendor, image(8192, offset=0))

    def test_rejects_invalid_vendor_header(self):
        with self.assertRaisesRegex(ValueError, 'vendor_boot'):
            boot.pack(self.stock, b'garbage', image(8192))


if __name__ == '__main__':
    unittest.main()
