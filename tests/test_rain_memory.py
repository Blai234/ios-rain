"""Make the memory preflight reject reservations hidden inside a RAM bank."""
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
import check_rain_memory  # noqa: E402
from check_rain_memory import check_iomem  # noqa: E402


class RainMemoryTest(unittest.TestCase):
    MAP = '''80000000-13fffffff : System RAM
  f3c00000-ffbfffff : reserved
'''

    def test_observed_reserved_region_is_above_new_window(self):
        result = check_iomem(self.MAP)
        self.assertEqual(result['end'], 0xf0000000)
        self.assertEqual(result['start'], 0x80000000)
        self.assertEqual(result['size'], 0x70000000)

    def test_the_window_base_is_twig_aligned(self):
        # xnu's physical aperture slides on 32 MB twig boundaries
        # (arm_vm_physmap_slide preserves each PA's offset inside its
        # twig), so the base has to be twig aligned. A base that is only
        # 16 MB aligned (0x83000000) hangs the kernel before it draws
        # anything.
        import mkadt
        import validate_rain_payload
        check_rain_payload = validate_rain_payload
        for base in (mkadt.RAIN_PHYS_BASE, validate_rain_payload.PHYS_BASE,
                     check_rain_memory.PHYS_BASE):
            self.assertEqual(base % validate_rain_payload.TWIG_SIZE, 0)
        with self.assertRaisesRegex(ValueError, 'twig aligned'):
            check_rain_payload.validate(b'', base=0x83000000, size=0x40000000)

    def test_rejects_previous_window(self):
        # The 1.2 GiB window the port started with reached into the
        # reservation and was retired.
        with self.assertRaisesRegex(ValueError, 'overlaps reserved'):
            check_iomem(self.MAP, base=0xb0000000, size=0x4d000000)

    def test_rejects_undocumented_hole(self):
        with self.assertRaisesRegex(ValueError, 'not all System RAM'):
            check_iomem('80000000-8fffffff : System RAM\n', size=0x40000000)

    def test_rejects_a_reservation_inside_the_new_window(self):
        # A dynamic pool inside the window would be taken away from the
        # userland, so the preflight has to refuse it.
        with self.assertRaisesRegex(ValueError, 'overlaps reserved'):
            check_iomem('80000000-13fffffff : System RAM\n'
                        '  90000000-90ffffff : reserved\n')

    def test_the_shim_and_the_tools_agree_on_the_window_end(self):
        # The shim refuses a window that reaches into the reserved region.
        loader = (ROOT / 'shim' / 'loader.c').read_text(encoding='utf-8')
        self.assertIn('0xf0000000ULL', loader)
        import check_rain_memory
        import validate_rain_payload
        self.assertEqual(check_rain_memory.PHYS_BASE, validate_rain_payload.PHYS_BASE)
        self.assertEqual(check_rain_memory.MEM_SIZE, validate_rain_payload.MEM_SIZE)
        self.assertEqual(validate_rain_payload.PHYS_BASE + validate_rain_payload.MEM_SIZE,
                         validate_rain_payload.WINDOW_MAX_END)


if __name__ == '__main__':
    unittest.main()
