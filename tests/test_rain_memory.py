"""Make the memory preflight reject reservations hidden inside a RAM bank."""
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from check_rain_memory import check_iomem  # noqa: E402


class RainMemoryTest(unittest.TestCase):
    MAP = '''80000000-13fffffff : System RAM
  f3c00000-ffbfffff : reserved
'''

    def test_observed_reserved_region_is_above_new_window(self):
        self.assertEqual(check_iomem(self.MAP)['end'], 0xf0000000)

    def test_rejects_previous_window(self):
        with self.assertRaisesRegex(ValueError, 'overlaps reserved'):
            check_iomem(self.MAP, size=0x4d000000)

    def test_rejects_undocumented_hole(self):
        with self.assertRaisesRegex(ValueError, 'not all System RAM'):
            check_iomem('80000000-bfffffff : System RAM\n', size=0x40000000)


if __name__ == '__main__':
    unittest.main()
