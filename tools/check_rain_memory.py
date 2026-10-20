#!/usr/bin/env python3
"""Check Rain's proposed XNU RAM window against a live Android /proc/iomem.

This is a preflight for the currently connected phone, not a guarantee about
bootloader carve-outs or a future boot's dynamic reservation placement.
"""
import argparse
import re
import subprocess
from pathlib import Path

PHYS_BASE = 0x83000000
MEM_SIZE = 0x6d000000
LINE = re.compile(r'^\s*([0-9a-fA-F]+)-([0-9a-fA-F]+)\s*:\s*(.+)$')


def check_iomem(data, base=PHYS_BASE, size=MEM_SIZE):
    end = base + size
    regions = []
    for line in data.splitlines():
        match = LINE.match(line)
        if match:
            start, last = int(match[1], 16), int(match[2], 16)
            if last < start:
                raise ValueError('reversed /proc/iomem range')
            regions.append((start, last + 1, match[3].strip()))
    if not regions:
        raise ValueError('no readable /proc/iomem regions')
    banks = [(start, stop) for start, stop, name in regions if name == 'System RAM']
    cursor = base
    for start, stop in sorted(banks):
        if start <= cursor < stop:
            cursor = min(end, stop)
        if cursor == end:
            break
    if cursor != end:
        raise ValueError(f'Rain window is not all System RAM: gap at 0x{cursor:x}')
    collisions = [(start, stop, name) for start, stop, name in regions
                  if name != 'System RAM' and start < end and base < stop]
    if collisions:
        start, stop, name = collisions[0]
        raise ValueError(f'Rain window overlaps {name} at 0x{start:x}-0x{stop - 1:x}')
    return {'start': base, 'end': end, 'size': end - base, 'banks': len(banks)}


def read_iomem(adb):
    """The live /proc/iomem, with or without a root shell on the device."""
    for command in (['su', '-c', 'cat /proc/iomem'], ['cat', '/proc/iomem']):
        try:
            return subprocess.check_output([str(adb), 'exec-out', *command],
                                           timeout=20).decode('ascii')
        except (subprocess.CalledProcessError, subprocess.TimeoutExpired):
            continue
    raise SystemExit('could not read /proc/iomem over adb')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument('--adb', type=Path, help='path to adb executable; reads the connected phone')
    source.add_argument('--iomem', type=Path, help='saved /proc/iomem text')
    parser.add_argument('--base', type=lambda v: int(v, 0), default=PHYS_BASE)
    parser.add_argument('--size', type=lambda v: int(v, 0), default=MEM_SIZE)
    args = parser.parse_args()
    if args.adb:
        data = read_iomem(args.adb)
    else:
        data = args.iomem.read_text(encoding='ascii')
    result = check_iomem(data, base=args.base, size=args.size)
    print(f"Rain RAM window 0x{result['start']:x}-0x{result['end'] - 1:x} "
          f"({result['size'] >> 20} MiB) is free in this Android /proc/iomem snapshot")


if __name__ == '__main__':
    main()
