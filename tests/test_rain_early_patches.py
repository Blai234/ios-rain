"""Rain's early XNU console must not map the inherited Sweet framebuffer."""
import sys
import subprocess
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
from rewrite_rain_xnu_patch import rewrite  # noqa: E402


class EarlyFramebufferPatchTest(unittest.TestCase):
    def test_unchanged_patches_copy_non_utf8_bytes(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / '0009-binary.patch'
            destination = Path(directory) / 'rewritten.patch'
            content = b'header\n\xd2\x00\xff\n'
            source.write_bytes(content)
            subprocess.run([sys.executable, str(ROOT / 'tools' / 'rewrite_rain_xnu_patch.py'),
                            str(source), str(destination)], check=True)
            self.assertEqual(destination.read_bytes(), content)

    def test_both_dependent_patches_use_rain_geometry(self):
        patches = ROOT / 'xnu' / 'patches'
        for prefix in ('0010-', '0012-'):
            source = next(patches.glob(prefix + '*.patch'))
            result = rewrite(source.name, source.read_text(encoding='utf-8'))
            self.assertIn('0x5c000000', result)
            self.assertIn('EARLY_WIDTH 720u', result)
            self.assertIn('EARLY_HEIGHT 1650u', result)
            self.assertIn('2880u / 4', result)
            self.assertNotIn('0x9c000000', result)
            self.assertNotIn('EARLY_WIDTH 1080u', result)
            self.assertNotIn('EARLY_HEIGHT 2400u', result)
            self.assertIn('stage * 32; x < (stage + 1) * 32', result)


if __name__ == '__main__':
    unittest.main()
