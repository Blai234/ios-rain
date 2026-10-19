#!/usr/bin/env python3
"""Read small Redmi 10C recovery partitions over adb without writing the phone."""
import argparse
import hashlib
import json
import subprocess
from pathlib import Path

PARTITIONS = (
    'persist', 'modemst1', 'modemst2', 'fsg', 'fsc',
    'boot_a', 'boot_b', 'dtbo_a', 'dtbo_b', 'vbmeta_a', 'vbmeta_b',
    'vendor_boot_a', 'vendor_boot_b',
)
MAX_BYTES = 200 * 1024 * 1024


def adb_read(adb, args):
    result = subprocess.run([adb, *args], capture_output=True, check=True)
    return result.stdout


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--adb', required=True, help='path to adb executable')
    parser.add_argument('--output', required=True, type=Path, help='private backup directory')
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    manifest = {}
    for name in PARTITIONS:
        block = f'/dev/block/by-name/{name}'
        size = int(adb_read(args.adb, ['shell', 'su', '-c', f'blockdev --getsize64 {block}']).strip())
        if size <= 0 or size > MAX_BYTES or size % 4096:
            raise RuntimeError(f'{name}: unexpected partition size {size}')
        block_size = 1024 * 1024 if size % (1024 * 1024) == 0 else 4096
        count = size // block_size
        target = args.output / f'{name}.img'
        partial = args.output / f'{name}.partial'
        if target.exists() or partial.exists():
            raise FileExistsError(f'{target} or {partial} already exists; refusing overwrite')
        digest = hashlib.sha256()
        actual = 0
        # On this Magisk/adb combination dd's progress text otherwise lands in
        # stdout beside the raw bytes. Explicit count also bounds the read.
        command = [args.adb, 'exec-out', 'su', '-c',
                   f'dd if={block} bs={block_size} count={count} status=none']
        with subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE) as process:
            with partial.open('wb') as output:
                while chunk := process.stdout.read(1024 * 1024):
                    actual += len(chunk)
                    if actual > size:
                        process.kill()
                        raise RuntimeError(f'{name}: received more than partition size')
                    output.write(chunk)
                    digest.update(chunk)
            error = process.stderr.read().decode('utf-8', 'replace')
            if process.wait() != 0 or actual != size:
                raise RuntimeError(f'{name}: adb/dd failed or short read ({actual}/{size}): {error}')
        partial.rename(target)
        manifest[name] = {'bytes': size, 'sha256': digest.hexdigest()}
        print(f'{name}: {size} bytes saved and hashed')
    (args.output / 'SHA256.json').write_text(json.dumps(manifest, indent=2) + '\n', encoding='utf-8')


if __name__ == '__main__':
    main()
