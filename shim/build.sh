#!/bin/bash
# Build the shim and wrap it in the target's Android boot image format.
# The DTB and vendor ramdisk come from the matching vendor_boot slot.
set -euo pipefail
cd "$(dirname "$0")"
CC=aarch64-linux-gnu-gcc
OBJCOPY=aarch64-linux-gnu-objcopy
CFLAGS="-O2 -ffreestanding -nostdlib -fno-pic -fno-jump-tables -mgeneral-regs-only -mstrict-align -fno-stack-protector -Wall -Wextra"
case "${TARGET:-topaz}" in
	rain) CFLAGS="$CFLAGS -DRAIN"; HEADER_VERSION=3; SOURCES="start.S shim.c console.c mmu.c fdt.c loader.c"; OBJECTS="out/start.o out/shim.o out/console.o out/mmu.o out/fdt.o out/loader.o" ;;
	topaz) HEADER_VERSION=4; SOURCES="start.S shim.c console.c mmu.c fdt.c loader.c ufs.c"; OBJECTS="out/start.o out/shim.o out/console.o out/mmu.o out/fdt.o out/loader.o out/ufs.o" ;;
	*) echo "unsupported TARGET: $TARGET" >&2; exit 2 ;;
esac
mkdir -p out
for f in $SOURCES; do
	$CC $CFLAGS -c $f -o out/${f%.*}.o
done
# The image runs wherever ABL puts it with no relocation pass: only the
# header's image_size (start.o, linked at 0) may be an absolute address.
abs=$(aarch64-linux-gnu-readelf -r ${OBJECTS#out/start.o } | grep -c ABS64 || true)
[ "$abs" = 0 ] || { echo "error: $abs absolute relocations in C objects" >&2; exit 1; }
$CC $CFLAGS -static -T shim.ld -Wl,--build-id=none -Wl,--no-warn-rwx-segments -Wl,-N \
	$OBJECTS -o out/shim.elf
$OBJCOPY -O binary out/shim.elf out/Image
# ABL copies the file; pad to image_size so .bss/stacks exist as zeroed bytes.
size=$((16#$(aarch64-linux-gnu-nm out/shim.elf | awk '$3=="_end"{print $1}')))
truncate -s "$size" out/Image
# Ramdisk: an xnu payload (tools/mkpayload.py) if given as $1, else an empty
# newc cpio (ABL dislikes a zero-size ramdisk on some builds) -> diagnostics.
if [ -n "${1:-}" ]; then
	# topaz ABL drops the v4 boot ramdisk: append the payload to the Image at
	# the first 4K boundary after _end (loader.c) and grow image_size.
	truncate -s $(( (size + 0xfff) & ~0xfff )) out/Image
	cat "$1" >> out/Image
	python3 -c 'import os,struct,sys; f=open(sys.argv[1],"r+b"); f.seek(16); f.write(struct.pack("<Q", os.path.getsize(sys.argv[1])))' out/Image
fi
if [ "${TARGET:-topaz}" = rain ]; then
	: "${RAIN_STOCK_BOOT:?set RAIN_STOCK_BOOT to the backed-up active boot image}"
	: "${RAIN_STOCK_VENDOR_BOOT:?set RAIN_STOCK_VENDOR_BOOT to its matching vendor_boot image}"
	python3 ../tools/pack_rain_boot.py --stock-boot "$RAIN_STOCK_BOOT" \
		--stock-vendor-boot "$RAIN_STOCK_VENDOR_BOOT" \
		--kernel out/Image --output out/shim-boot.img
else
	(cd out && rm -rf rd && mkdir rd && cd rd && find . | cpio -o -H newc --quiet | gzip -9 > ../ramdisk.bin)
	${MKBOOTIMG:-python3 /home/makr/work/topaz/mkbootimg_src/mkbootimg.py} --header_version "$HEADER_VERSION" --kernel out/Image --ramdisk out/ramdisk.bin \
		--os_version 13.0.0 --os_patch_level 2025-01 \
		--cmdline "console=null" -o out/shim-boot.img
fi
# Host render of the console layout.
gcc -O1 -Wall ${TARGET:+-D${TARGET^^}} -o out/host_test console.c host_test.c && ./out/host_test
ls -l out/Image out/shim-boot.img
