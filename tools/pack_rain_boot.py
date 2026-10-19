#!/usr/bin/env python3
"""Package a Rain shim in the connected phone's stock Android boot v3 layout.

This only writes an output file on the host. It copies the stock boot header
and boot ramdisk, changes kernel_size, and supplies a gzip-compressed shim.
The original vendor_boot, DTBO, partitions and AVB footer are untouched.
"""
import argparse
import gzip
import struct
from pathlib import Path

PAGE = 4096
V3_HEADER_SIZE = 1580


def align(n):
    return (n + PAGE - 1) & ~(PAGE - 1)


def read_stock_boot(data):
    if len(data) < PAGE or data[:8] != b'ANDROID!':
        raise ValueError('expected an Android boot image')
    kernel_size, ramdisk_size, _, header_size = struct.unpack_from('<4I', data, 8)
    version = struct.unpack_from('<I', data, 40)[0]
    if version != 3 or header_size != V3_HEADER_SIZE or data[24:40] != bytes(16):
        raise ValueError('expected canonical Android boot header v3')
    if not kernel_size or not ramdisk_size:
        raise ValueError('stock boot kernel and ramdisk must be nonempty')
    ramdisk_offset = PAGE + align(kernel_size)
    end = ramdisk_offset + align(ramdisk_size)
    if end > len(data):
        raise ValueError('stock boot payload exceeds image length')
    stock_kernel = data[PAGE:PAGE + kernel_size]
    if stock_kernel[:2] != b'\x1f\x8b':
        raise ValueError('this Rain stock kernel is expected to use gzip')
    stock_image = gzip.decompress(stock_kernel)
    if stock_image[56:60] != b'ARM\x64':
        raise ValueError('stock kernel lacks the ARM64 Image header')
    return data[:PAGE], data[ramdisk_offset:ramdisk_offset + ramdisk_size], stock_image


def pack(stock_boot, vendor_boot, image):
    if len(vendor_boot) < PAGE or vendor_boot[:8] != b'VNDRBOOT':
        raise ValueError('expected a matching stock vendor_boot image')
    if struct.unpack_from('<II', vendor_boot, 8) != (3, PAGE):
        raise ValueError('expected vendor_boot header v3 with 4096-byte pages')
    header, ramdisk, stock_image = read_stock_boot(stock_boot)
    if len(image) < 64 or image[56:60] != b'ARM\x64':
        raise ValueError('shim lacks the ARM64 Image header')
    stock_offset, _, stock_flags = struct.unpack_from('<QQQ', stock_image, 8)
    offset, declared_size, flags = struct.unpack_from('<QQQ', image, 8)
    if (offset, flags) != (stock_offset, stock_flags):
        raise ValueError('shim placement offset or flags differ from stock kernel')
    if declared_size != len(image):
        raise ValueError('shim Image length differs from its declared image_size')
    compressed = gzip.compress(image, compresslevel=9, mtime=0)
    out_header = bytearray(header)
    struct.pack_into('<I', out_header, 8, len(compressed))
    candidate = (bytes(out_header) + compressed + bytes(align(len(compressed)) - len(compressed)) +
                 ramdisk + bytes(align(len(ramdisk)) - len(ramdisk)))
    if len(candidate) > len(stock_boot):
        raise ValueError('candidate exceeds the backed-up boot partition size')
    check_header, check_ramdisk, check_image = read_stock_boot(candidate)
    if check_ramdisk != ramdisk or check_image != image or check_header[12:PAGE] != header[12:PAGE]:
        raise AssertionError('candidate round-trip verification failed')
    return candidate


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--stock-boot', type=Path, required=True)
    parser.add_argument('--stock-vendor-boot', type=Path, required=True)
    parser.add_argument('--kernel', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if args.output.resolve() in (args.stock_boot.resolve(), args.stock_vendor_boot.resolve()):
        parser.error('output must not overwrite a stock backup')
    result = pack(args.stock_boot.read_bytes(), args.stock_vendor_boot.read_bytes(),
                  args.kernel.read_bytes())
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(result)
    print(f'Wrote local Rain boot-v3 candidate: {args.output} ({len(result)} bytes)')


if __name__ == '__main__':
    main()
