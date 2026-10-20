#!/usr/bin/env python3
"""Prepare Rain display-geometry and console test images.

The Rain device tree now presents the iPhone X canvas (1125x2436) to the
userland, which is what the kernel reports through GetDisplaySize. Without
`sweetfb_scale=1` the kernel shows the centre crop of that canvas on the
720x1650 panel; with it the canvas is resampled into the panel.

The selected variants differ only in boot arguments, so a phone test can
isolate display scaling and console muting. Nothing is flashed: the result is
a temporary boot image.
"""
import argparse
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import adt  # noqa: E402
import mkadt  # noqa: E402
import mkpayload  # noqa: E402
from validate_rain_payload import validate  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]

# The command line of the last Rain boot. rainquietscaler=1 is left out on
# purpose: the AppleM2ScalerCSCDriver message has to stay visible to tell
# whether the canvas fix removed the scaler lookup.
CMDLINE = ('debug=0xc serial=3 cpus=1 keepsyms=1 -enable_kprintf_spam -noprogress '
           'rd=ufsroot0 unentitled_ios_sim_launch=1 ufscow=1 rootrw=1 '
           'launchd_unsecure_cache=1 sweetnull=SpringBoard sweetfb_noconsole=1 '
           'rainseedmigration=1')

# The console variant keeps the kernel console alive. sweetfb_noconsole=1
# mutes it on the first swapped frame and the persistent log is off in the
# volatile overlay mode, so this is the only way to read the log while the
# userland is stuck.
CONSOLE_CMDLINE = CMDLINE.replace(' sweetfb_noconsole=1', '')

# cpus=4 starts the four Gold cores. The shim already prepares their GIC
# redistributors (gold_gicr_prepare enables the timers and SGI1 for each),
# and the 0x100-style affinity in the device tree works on Rain because the
# GIC's Aff2/Aff3 SGI filters are "any". The four-CPU boots so far
# corrupted the HFS catalog, most likely because the volatile overlay
# filled up: it stores whole 4 KiB blocks while HFS writes 512-byte
# sectors, so it fills eight times too fast and a refused write in the
# middle of a catalog update leaves the catalog inconsistent.
CPUS4_CMDLINE = CMDLINE.replace('cpus=1', 'cpus=4')
CPUS4_CONSOLE_CMDLINE = CONSOLE_CMDLINE.replace('cpus=1', 'cpus=4')

VARIANTS = (('crop', CMDLINE), ('scaled', CMDLINE + ' sweetfb_scale=1'),
            ('console', CONSOLE_CMDLINE),
            ('scaled-console', CONSOLE_CMDLINE + ' sweetfb_scale=1'),
            ('cpus4', CPUS4_CMDLINE),
            ('cpus4console', CPUS4_CONSOLE_CMDLINE))


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def build_adt(path, seed=None, base=None, size=None):
    """A Rain tree with the storage node the volatile overlay boot needs."""
    tree = mkadt.build(seed=seed, rain=True, ufs=True,
                       rain_base=base, rain_size=size)
    blob = adt.serialize(tree)
    path.write_bytes(blob)
    return blob


def kernel_seed(kernel_bytes):
    """A deterministic ADT seed, so the same kernel gives the same image.

    The seed feeds the kernel's PRNG. Deriving it from the kernel digest
    keeps it unpredictable per build and makes the boot image reproducible.
    """
    return hashlib.sha256(kernel_bytes + b'rain-adt-seed').digest() * 2


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--kernel', type=Path, required=True,
                        help='the kernel.development.sweet from the Rain CI build')
    parser.add_argument('--outdir', type=Path, default=ROOT / 'xnu' / 'out-rain-ci')
    parser.add_argument('--adt', type=Path, help='use this ADT instead of building one')
    parser.add_argument('--stock-boot', type=Path,
                        default=ROOT / 'backup' / 'rain-2026-10-19' / 'boot_a.img')
    parser.add_argument('--stock-vendor-boot', type=Path,
                        default=ROOT / 'backup' / 'rain-2026-10-19' / 'vendor_boot_a.img')
    parser.add_argument('--llvm-bin', type=Path)
    parser.add_argument('--base', type=lambda v: int(v, 0),
                        help='Rain RAM window base (default from tools/mkadt.py)')
    parser.add_argument('--size', type=lambda v: int(v, 0),
                        help='Rain RAM window size (default from tools/mkadt.py)')
    parser.add_argument('--tag', default='', help='suffix for the output files')
    parser.add_argument('--variant', choices=[name for name, _ in VARIANTS],
                        help='build only this variant')
    parser.add_argument('--image', action='store_true',
                        help='also build the boot-v3 image for each variant')
    args = parser.parse_args()

    if not args.kernel.is_file():
        parser.error(f'{args.kernel} missing; download the Rain CI kernel first')
    args.outdir.mkdir(parents=True, exist_ok=True)
    adt_path = args.adt or (args.outdir / 'rain-display.adt')
    kernel_bytes = args.kernel.read_bytes()
    if args.adt:
        adt_blob = args.adt.read_bytes()
    else:
        adt_blob = build_adt(adt_path, kernel_seed(kernel_bytes),
                             base=args.base, size=args.size)
    print(f'ADT {adt_path}: {len(adt_blob)} bytes')

    report = {'kernel': str(args.kernel), 'kernel_sha256': sha256(kernel_bytes),
              'adt': str(adt_path), 'adt_sha256': sha256(adt_blob), 'variants': {}}
    for name, cmdline in VARIANTS:
        if args.variant and name != args.variant:
            continue
        blob, info = mkpayload.build(args.kernel, adt_path, cmdline)
        checks = validate(blob, allow_volatile_ufs=True, base=args.base, size=args.size)
        payload = args.outdir / f'rain-display-{name}{args.tag}.payload'
        payload.write_bytes(blob)
        entry = {'command_line': cmdline, 'payload': str(payload),
                 'payload_sha256': sha256(blob), 'payload_bytes': len(blob),
                 'preflight': checks, 'info': {k: v for k, v in info.items() if k != 'segs'}}
        if args.image:
            entry['image'] = build_image(args, payload, f'{name}{args.tag}')
        report['variants'][name] = entry
        print(f'{name}: {payload} ({len(blob)} bytes) {entry["payload_sha256"]}')
        print(f'  {cmdline}')
    (args.outdir / f'rain-display{args.tag}-test.json').write_text(json.dumps(report, indent=2) + '\n')
    print(f'report: {args.outdir / f"rain-display{args.tag}-test.json"}')


def build_image(args, payload, name):
    """Wrap the payload in a temporary boot-v3 image with the stock header."""
    import build_rain_shim

    outdir = args.outdir / f'rain-display-{name}-shim'
    build_rain_shim.build(args.llvm_bin, outdir, args.stock_boot, args.stock_vendor_boot,
                          payload, allow_volatile_ufs=True,
                          base=args.base, size=args.size)
    image = outdir / 'shim-boot.img'
    return {'path': str(image), 'sha256': sha256(image.read_bytes()),
            'bytes': image.stat().st_size}


if __name__ == '__main__':
    main()
