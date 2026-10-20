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


def payload(rain=True, readonly_ufs=False, cmdline='', canvas=None):
    tree = mkadt.build(seed=b'0' * 64, rain=rain)
    if canvas is not None:
        disp = child(child(tree, 'arm-io'), 'disp0')
        disp.props = [(k, f, v) for k, f, v in disp.props
                      if k not in ('canvas-width', 'canvas-height')]
        disp.props.append(('canvas-width', 0, mkadt.u32(canvas[0])))
        disp.props.append(('canvas-height', 0, mkadt.u32(canvas[1])))
    if readonly_ufs:
        tree.children.append(mkadt.node('sweet-ufs', [
            ('compatible', mkadt.cstr('qcom,ufshc')),
            ('reg', mkadt.u64(0x04804000, 0x3000)),
        ]))
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
    data[0x48:0x48 + len(cmdline)] = cmdline.encode()
    data[adt_off:adt_off + len(device_tree)] = device_tree
    data.extend(bytes((-len(data)) & 7))
    return data


def child(parent, name):
    return next(n for n in parent.children
                if dict((k, v) for k, _, v in n.props)['name'] == name.encode() + b'\0')


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

    def test_readonly_ufs_requires_explicit_mode(self):
        data = payload(readonly_ufs=True, cmdline='rd=ufsroot0 unentitled_ios_sim_launch=1')
        with self.assertRaisesRegex(ValueError, 'must omit sweet-ufs'):
            check.validate(data)
        check.validate(data, allow_readonly_ufs=True)

    def test_readonly_ufs_rejects_write_flags(self):
        data = payload(readonly_ufs=True, cmdline='rd=ufsroot0 ufsrw=1')
        with self.assertRaisesRegex(ValueError, 'without physical write flags'):
            check.validate(data, allow_readonly_ufs=True)

    def test_volatile_ufs_requires_explicit_overlay(self):
        data = payload(readonly_ufs=True, cmdline='rd=ufsroot0 ufscow=1 rootrw=1')
        with self.assertRaisesRegex(ValueError, 'without write flags'):
            check.validate(data, allow_readonly_ufs=True)
        check.validate(data, allow_volatile_ufs=True)

    def test_volatile_ufs_rejects_physical_writes_and_duplicate_flags(self):
        for line in ('rd=ufsroot0 ufscow=1 rootrw=1 ufsrw=1',
                     'rd=ufsroot0 ufscow=1 rootrw=1 ufscow=0'):
            with self.subTest(line=line), self.assertRaises(ValueError):
                check.validate(payload(readonly_ufs=True, cmdline=line),
                               allow_volatile_ufs=True)

    def test_rejects_a_canvas_the_kernel_does_not_present(self):
        # A canvas that differs from the size SweetFramebuffer reports makes
        # backboardd look for the non-existent AppleM2ScalerCSCDriver.
        check.validate(payload())
        with self.assertRaisesRegex(ValueError, 'canvas'):
            check.validate(payload(canvas=(720, 1650)))

    def test_accepts_the_native_canvas_with_the_native_boot_argument(self):
        check.validate(payload(cmdline='sweetfb_native=1', canvas=(720, 1650)))


if __name__ == '__main__':
    unittest.main()
