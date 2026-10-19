#!/usr/bin/env python3
"""Validate a storage-free Rain XNU payload before embedding it in a boot image.

This checks the loader's bounds contract and the Rain ADT. It cannot prove that
the Mach-O code boots or that the selected XNU patches were compiled into it.
"""
import argparse
import struct
from pathlib import Path

import adt

BASE_HEADER = 0x2a8
SEG_SIZE = 32
MAX_SEGS = 64
MAX_ADT = 0x100000
PHYS_BASE = 0xb0000000
MEM_SIZE = 0x40000000


def prop(node, name):
    return next((v for key, _, v in node.props if key == name), None)


def child(node, name):
    return next((n for n in node.children if prop(n, 'name') == name.encode() + b'\0'), None)


def validate(data):
    if len(data) > 0x8000000:
        raise ValueError('payload exceeds diagnostic Image size limit')
    if len(data) < BASE_HEADER or data[:8] != b'SWEETXNU':
        raise ValueError('missing SWEETXNU payload header')
    version, nsegs = struct.unpack_from('<II', data, 8)
    if version != 1 or not 1 <= nsegs <= MAX_SEGS:
        raise ValueError('unsupported payload version or segment count')
    header = BASE_HEADER + SEG_SIZE * nsegs
    if len(data) < header:
        raise ValueError('truncated segment table')
    virt, entry, adt_off, adt_size, kernel_end, phys, mem = struct.unpack_from('<7Q', data, 0x10)
    if (phys, mem) != (PHYS_BASE, MEM_SIZE):
        raise ValueError('payload selects the wrong Rain RAM window')
    if virt == 0 or kernel_end <= virt or not virt <= entry < kernel_end:
        raise ValueError('invalid kernel virtual range')
    kernel_bytes = kernel_end - virt
    if kernel_bytes + adt_size + 0x8000 > mem:
        raise ValueError('kernel, ADT and boot args exceed Rain RAM')
    if (adt_off & 7 or adt_off < header or not 0 < adt_size <= MAX_ADT or
            adt_off + adt_size > len(data) or
            adt_off + ((adt_size + 7) & ~7) > len(data)):
        raise ValueError('ADT is outside payload bounds')
    ranges = []
    for i in range(nsegs):
        vmaddr, vmsize, file_off, file_size = struct.unpack_from('<4Q', data, BASE_HEADER + SEG_SIZE * i)
        if vmaddr < virt or file_off < header or file_off > len(data):
            raise ValueError(f'segment {i} starts outside the payload or kernel')
        if file_off + ((file_size + 7) & ~7) > len(data):
            raise ValueError(f'segment {i} reads past payload end')
        offset = vmaddr - virt
        if offset + vmsize > kernel_bytes or ((file_size + 7) & ~7) > vmsize:
            raise ValueError(f'segment {i} exceeds kernel allocation')
        ranges.append((offset, offset + vmsize))
    if not any(lo <= entry - virt < hi for lo, hi in ranges):
        raise ValueError('entry point is outside loadable segments')

    tree, used = adt.parse(data[adt_off:adt_off + adt_size])
    if used != adt_size or b'xiaomi,rain\0' not in (prop(tree, 'compatible') or b''):
        raise ValueError('ADT is not a Rain device tree')
    chosen = child(tree, 'chosen')
    fb = child(tree, 'sweet-fbcon')
    if chosen is None or fb is None or child(tree, 'sweet-ufs') is not None:
        raise ValueError('Rain ADT needs chosen and framebuffer, without sweet-ufs')
    if (prop(chosen, 'dram-base') != struct.pack('<Q', PHYS_BASE) or
            prop(chosen, 'dram-size') != struct.pack('<Q', MEM_SIZE)):
        raise ValueError('ADT RAM window differs from payload')
    if (prop(fb, 'reg') != struct.pack('<QQ', 0x5c000000, 0xf00000) or
            prop(fb, 'width') != struct.pack('<I', 720) or
            prop(fb, 'height') != struct.pack('<I', 1650) or
            prop(fb, 'stride') != struct.pack('<I', 2880)):
        raise ValueError('ADT framebuffer is not the observed Rain layout')
    return {'segments': nsegs, 'payload_bytes': len(data), 'kernel_bytes': kernel_bytes,
            'entry_pa': phys + entry - virt, 'adt_bytes': adt_size}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('payload', type=Path)
    args = parser.parse_args()
    result = validate(args.payload.read_bytes())
    print(f"Rain payload checked: {result['segments']} segments, "
          f"{result['payload_bytes']} bytes, entry PA 0x{result['entry_pa']:x}")


if __name__ == '__main__':
    main()
