#!/usr/bin/env python3
"""Build and package the storage-silent Rain shim with host LLVM tools.

No device commands are issued. The result is an offline boot candidate, not a
validated phone boot or an iOS kernel.
"""
import argparse
import os
import shutil
import struct
import subprocess
from pathlib import Path

from pack_rain_boot import pack
from validate_rain_payload import validate as validate_payload

ROOT = Path(__file__).resolve().parents[1]
SHIM = ROOT / 'shim'
SOURCES = ('start.S', 'shim.c', 'console.c', 'mmu.c', 'fdt.c', 'loader.c')


def tool(name, directory):
    suffix = '.exe' if os.name == 'nt' else ''
    candidates = ([directory / (name + suffix)] if directory else [])
    if os.name == 'nt':
        candidates.append(Path(os.environ.get('ProgramFiles', 'C:/Program Files')) /
                          'LLVM' / 'bin' / (name + suffix))
    for candidate in candidates:
        if candidate.is_file():
            return str(candidate)
    found = shutil.which(name)
    if not found:
        raise FileNotFoundError(f'{name} missing; set --llvm-bin to an LLVM bin directory')
    return found


def run(*args):
    subprocess.run(args, check=True)


def build(llvm_bin, output, stock_boot, vendor_boot, payload=None):
    output.mkdir(parents=True, exist_ok=True)
    clang = tool('clang', llvm_bin)
    ld = tool('ld.lld', llvm_bin)
    objcopy = tool('llvm-objcopy', llvm_bin)
    nm = tool('llvm-nm', llvm_bin)
    readobj = tool('llvm-readobj', llvm_bin)
    objects = []
    common = (clang, '--target=aarch64-none-elf', '-O2', '-ffreestanding', '-nostdlib',
              '-fno-pic', '-fno-jump-tables', '-mgeneral-regs-only', '-mstrict-align',
              '-fno-stack-protector', '-DRAIN', '-Wall', '-Wextra')
    for source in SOURCES:
        obj = output / (Path(source).stem + '.o')
        run(*common, '-c', str(SHIM / source), '-o', str(obj))
        objects.append(obj)
    relocs = subprocess.check_output([readobj, '--relocations',
                                      *map(str, objects[1:])], text=True)
    if 'R_AARCH64_ABS64' in relocs:
        raise ValueError('absolute C relocation in a position-independent shim')
    elf = output / 'shim.elf'
    run(ld, '-m', 'aarch64elf', '-static', '-T', str(SHIM / 'shim.ld'),
        '--build-id=none', '-N', *map(str, objects), '-o', str(elf))
    symbols = subprocess.check_output([nm, str(elf)], text=True)
    if ' test_ufs\n' in symbols or ' ufs_wr\n' in symbols:
        raise ValueError('Rain shim unexpectedly contains a UFS probe')
    ends = [int(line.split()[0], 16) for line in symbols.splitlines()
            if line.split()[-1:] == ['_end']]
    if len(ends) != 1:
        raise ValueError('missing unique _end symbol')
    image_file = output / 'Image'
    run(objcopy, '-O', 'binary', str(elf), str(image_file))
    data = bytearray(image_file.read_bytes())
    if len(data) > ends[0]:
        raise ValueError('ELF load data exceeds declared Image size')
    data.extend(bytes(ends[0] - len(data)))
    if payload:
        payload_bytes = payload.read_bytes()
        validate_payload(payload_bytes)
        data.extend(bytes((-len(data)) % 4096))
        data.extend(payload_bytes)
        struct.pack_into('<Q', data, 16, len(data))
    if len(data) > 0x8000000:
        raise ValueError('shim Image exceeds loader size limit')
    if data[56:60] != b'ARM\x64' or struct.unpack_from('<Q', data, 16)[0] != len(data):
        raise ValueError('invalid shim ARM64 Image header')
    image_file.write_bytes(data)
    candidate = pack(stock_boot.read_bytes(), vendor_boot.read_bytes(), data)
    image_out = output / 'shim-boot.img'
    image_out.write_bytes(candidate)
    print(f'Built local Rain shim: {image_file} ({len(data)} bytes)')
    print(f'Packaged boot-v3 candidate: {image_out} ({len(candidate)} bytes)')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--stock-boot', type=Path, required=True)
    parser.add_argument('--stock-vendor-boot', type=Path, required=True)
    parser.add_argument('--llvm-bin', type=Path)
    parser.add_argument('--output', type=Path, default=SHIM / 'out')
    parser.add_argument('--payload', type=Path, help='optional prepared XNU payload')
    args = parser.parse_args()
    build(args.llvm_bin, args.output, args.stock_boot, args.stock_vendor_boot, args.payload)


if __name__ == '__main__':
    main()
