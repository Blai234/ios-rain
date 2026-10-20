#!/usr/bin/env python3
"""Dump the Rain GENI SPI and pinctrl registers over ADB, read only.

The phone's touch controller is on the GENI SPI block at 0x4a80000, which the
Android fts_ts driver programs. Reading the block while that driver is bound
shows the register values a working setup has, which is what the XNU driver
has to reproduce. Nothing on the device is changed: devmem only reads.
"""
import argparse
import re
import subprocess
import sys

# The GENI SPI core, the TLMM (pinctrl) and the clock controller.
GENI = 0x04a80000
GENI_LEN = 0x100
TLMM = 0x00400000
TLMM_STRIDE = 0x1000
GCC = 0x01400000
GCC_LEN = 0x2000


def sh(adb, script):
    result = subprocess.run([adb, 'exec-out', 'sh', '-c', script],
                            capture_output=True, timeout=120)
    if result.returncode:
        raise SystemExit(result.stderr.decode(errors='replace') or 'adb failed')
    return result.stdout.decode(errors='replace')


def dump(adb, base, length, label):
    """devmem one word at a time: the recovery has no /dev/mem."""
    script = (
        'i=0; '
        f'while [ $i -lt {length} ]; do '
        f'printf "0x%08x %s\\n" $(( {base} + i )) "$(devmem $(( {base} + i )) 2>/dev/null)"; '
        'i=$((i+4)); done')
    out = sh(adb, script)
    values = {}
    for line in out.splitlines():
        match = re.match(r'^(0x[0-9a-f]+)\s+(.*)$', line.strip())
        if not match:
            continue
        raw = match.group(2).strip()
        if raw.startswith('0x'):
            values[int(match.group(1), 16)] = int(raw, 16)
    print(f'--- {label} (0x{base:x}) ---')
    for address in sorted(values):
        print(f'  0x{address:08x}: 0x{values[address]:08x}')
    return values


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--adb', required=True)
    args = parser.parse_args()
    if not sh(args.adb, 'id -u').strip().endswith('0'):
        raise SystemExit('root adb is required')
    dump(args.adb, GENI, GENI_LEN, 'GENI SPI')
    for pin in (0, 1, 2, 3, 80, 86):
        dump(args.adb, TLMM + pin * TLMM_STRIDE, 0x10, f'TLMM gpio{pin}')
    dump(args.adb, GCC, GCC_LEN, 'GCC')


if __name__ == '__main__':
    main()
