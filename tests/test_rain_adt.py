"""Hardware invariants for the Redmi 10C bring-up tree."""
import struct
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import mkadt  # noqa: E402


def child(parent, name):
    return next(n for n in parent.children if dict((k, v) for k, _, v in n.props)['name'] == name.encode() + b'\0')


def prop(node, name):
    return dict((k, v) for k, _, v in node.props)[name]


class RainTreeTest(unittest.TestCase):
    def test_rain_is_storage_silent_and_within_live_ram(self):
        root = mkadt.build(seed=b'0' * 64, rain=True)
        chosen = child(root, 'chosen')
        fb = child(root, 'sweet-fbcon')
        disp = child(child(root, 'arm-io'), 'disp0')
        self.assertEqual(struct.unpack('<Q', prop(chosen, 'dram-base'))[0], 0xb0000000)
        self.assertEqual(struct.unpack('<Q', prop(chosen, 'dram-size'))[0], 0x40000000)
        self.assertLessEqual(0xb0000000 + 0x40000000, 0xf0000000)
        self.assertEqual(struct.unpack('<III', prop(fb, 'width') + prop(fb, 'height') + prop(fb, 'stride')), (720, 1650, 2880))
        self.assertEqual(struct.unpack('<II', prop(disp, 'canvas-width') + prop(disp, 'canvas-height')), (720, 1650))
        self.assertIn(b'xiaomi,rain\0', prop(root, 'compatible'))
        self.assertNotIn(b'sweet-ufs\0', [prop(n, 'name') for n in root.children])

    def test_topaz_defaults_are_preserved(self):
        root = mkadt.build(seed=b'0' * 64)
        fb = child(root, 'sweet-fbcon')
        self.assertEqual(struct.unpack('<III', prop(fb, 'width') + prop(fb, 'height') + prop(fb, 'stride')), (1080, 2400, 4320))
        self.assertIn(b'sweet-ufs\0', [prop(n, 'name') for n in root.children])

    def test_rain_rejects_topaz_high_memory(self):
        with self.assertRaises(ValueError):
            mkadt.build(seed=b'0' * 64, rain=True, highmem=True)


if __name__ == '__main__':
    unittest.main()
