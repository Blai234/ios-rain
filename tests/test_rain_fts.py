"""The Rain touch driver has to parse before a CI kernel build is spent on it."""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
import check_rain_fts  # noqa: E402


class RainFtsTest(unittest.TestCase):
    def test_the_driver_parses_and_its_wiring_is_present(self):
        patch = ROOT / 'xnu' / 'patches' / '0082-zrain-zz-fts-touch.patch'
        self.assertTrue(patch.is_file(), 'the touch patch is missing')
        source = check_rain_fts.driver_source()
        self.assertIn('rain_touch_init', source)
        self.assertIn('fts_spi_xfer', source)
        self.assertIn('FTS_CHIP_ID_REG', source)
        # The patch has to add the file to the build and to call the driver
        # from the place where the other input drivers start.
        text = patch.read_text(encoding='utf-8')
        self.assertIn('bsd/dev/sweet_fts.c', text)
        self.assertIn('+bsd/dev/sweet_fts.c\t\t\tstandard', text)
        self.assertIn('+\train_touch_init();', text)
        self.assertEqual(check_rain_fts.main(), 0)


if __name__ == '__main__':
    unittest.main()
