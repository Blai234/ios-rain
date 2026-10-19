"""Host preflight should reject payloads that could leave Rain's RAM window."""
import struct
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'tools'))
import adt  # noqa: E402
import mkadt  # noqa: E402
import validate_rain_payload as check  # noqa: E402


def payload(rain=True):
    tree = mkadt.build(seed=b'0' * 64, rain=rain)
    device_tree = adt.serialize(tree)
    virt = 0xfffffff006000000
    header = check.BASE_HEADER + check.SEG_SIZE
    adt_off = (header + 64 + 15) & ~15
    data = bytearray(adt_off + len(device_tree))
    data[:8] = b'SWEETXNU'
    struct.pack_into('<II', data, 8, 1, 1)
    struct.pack_into('<7Q', data, 0x10, virt, virt + 0x100, adt_off, len(device_tree),
                     virt + 0x4000, check.PHYS_BASE, check.MEM_SIZE)
    struct.pack_into('<4Q', data, check.BASE_HEADER, virt, 0x4000, header, 64)
    data[adt_off:adt_off + len(device_tree)] = device_tree
    data.extend(bytes((-len(data)) & 7))
    return data


class RainPayloadTest(unittest.TestCase):
    def test_accepts_storage_free_rain_layout(self):
        result = check.validate(payload())
        self.assertEqual(result['entry_pa'], check.PHYS_BASE + 0x100)

    def test_rejects_source_past_end(self):
        data = payload()
        struct.pack_into('<Q', data, check.BASE_HEADER + 16, len(data) - 4)
        with self.assertRaisesRegex(ValueError, 'reads past'):
            check.validate(data)

    def test_rejects_segment_outside_kernel(self):
        data = payload()
        struct.pack_into('<Q', data, check.BASE_HEADER + 8, 0x8000)
        with self.assertRaisesRegex(ValueError, 'exceeds kernel'):
            check.validate(data)

    def test_rejects_topaz_tree(self):
        with self.assertRaisesRegex(ValueError, 'not a Rain'):
            check.validate(payload(rain=False))


if __name__ == '__main__':
    unittest.main()
