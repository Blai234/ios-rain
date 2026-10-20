/*
 * Milestone 4: act as iBoot for xnu.
 *
 * mkpayload.py already resolved the kernel's chained fixups and built the
 * ADT, so this only has to: find the payload in the ABL ramdisk, copy the
 * segments to phys_base + (vmaddr - virt_base), place the ADT and
 * boot_args behind the kernel, and jump to the entry point with the MMU
 * and caches off, x0 = boot_args (physical).
 */
#include <stdint.h>
#include "console.h"
#include "fdt.h"
#include "loader.h"

#define BOOT_LINE_LENGTH	608
#define PAGE_16K		0x4000UL
#define MAX_IMAGE_SIZE		0x8000000UL
#define MAX_PAYLOAD_SEGS	64U
#define MAX_ADT_SIZE		0x100000UL
/* Rain: the top of the kernel-managed RAM (see tools/mkadt.py). */
#define RAIN_WINDOW_MAX_END	0xf0000000ULL
/* xnu's physical aperture slides on 32 MB twigs. */
#define RAIN_WINDOW_TWIG	0x2000000ULL

struct payload_seg {
	uint64_t vmaddr, vmsize, file_off, file_size;
};

struct payload {
	char magic[8];
	uint32_t version, nsegs;
	uint64_t virt_base, entry_va, adt_off, adt_size, kernel_end;
	uint64_t phys_base, mem_size;
	char cmdline[BOOT_LINE_LENGTH];
	struct payload_seg segs[];
};

/* pexpert/pexpert/arm64/boot.h, Revision/Version 2 */
struct boot_video {
	uint64_t v_baseAddr, v_display, v_rowBytes, v_width, v_height, v_depth;
};

struct boot_args {
	uint16_t Revision, Version;
	uint64_t virtBase, physBase, memSize, topOfKernelData;
	struct boot_video Video;
	uint32_t machineType;
	uint64_t deviceTreeP;
	uint32_t deviceTreeLength;
	char CommandLine[BOOT_LINE_LENGTH];
	uint64_t bootFlags, memSizeActual;
};

_Static_assert(__builtin_offsetof(struct payload, segs) == 0x2a8, "payload header layout");
_Static_assert(__builtin_offsetof(struct boot_args, Video) == 40, "boot_args layout");
_Static_assert(__builtin_offsetof(struct boot_args, CommandLine) == 108, "boot_args layout");
_Static_assert(sizeof(struct boot_args) == 736, "boot_args layout");

/* MMU off: everything is Device memory, so copy in aligned 8-byte words. */
static void copy64(uintptr_t dst, uintptr_t src, uint64_t n)
{
	volatile uint64_t *d = (volatile uint64_t *)dst;
	volatile const uint64_t *s = (volatile const uint64_t *)src;
	for (uint64_t i = 0; i < (n + 7) / 8; i++)
		d[i] = s[i];
}

static void zero64(uintptr_t dst, uint64_t n)
{
	volatile uint64_t *d = (volatile uint64_t *)dst;
	for (uint64_t i = 0; i < n / 8; i++)
		d[i] = 0;
}

static int magic_ok(const char *m)
{
	static const char want[] = "SWEETXNU";
	for (int i = 0; i < 8; i++)
		if (m[i] != want[i])
			return 0;
	return 1;
}

typedef void (*xnu_entry_t)(uint64_t boot_args_pa);

/* build.sh appends the payload to the Image at the first 4K boundary after _end */
extern char _head[], _end[];

static const char *validate_payload(const struct payload *p, uint64_t available)
{
	const uint64_t base_header = __builtin_offsetof(struct payload, segs);
	if (available < base_header || p->version != 1 ||
	    p->nsegs == 0 || p->nsegs > MAX_PAYLOAD_SEGS)
		return "bad payload header";
	uint64_t header = base_header + (uint64_t)p->nsegs * sizeof(struct payload_seg);
	if (header > available || (p->adt_off & 7) ||
	    p->adt_off < header || p->adt_size == 0 || p->adt_size > MAX_ADT_SIZE ||
	    p->adt_off > available || ((p->adt_size + 7) & ~7ULL) > available - p->adt_off)
		return "bad payload bounds";
	if (p->virt_base == 0 || p->kernel_end < p->virt_base ||
	    p->entry_va < p->virt_base || p->entry_va >= p->kernel_end ||
	    p->mem_size < 2 * PAGE_16K)
		return "bad kernel range";
	uint64_t kernel_off = p->kernel_end - p->virt_base;
	if (kernel_off >= p->mem_size ||
	    p->adt_size + 2 * PAGE_16K > p->mem_size - kernel_off)
		return "kernel exceeds RAM window";
	for (uint32_t i = 0; i < p->nsegs; i++) {
		const struct payload_seg *s = &p->segs[i];
		if (s->vmaddr < p->virt_base || s->file_off < header ||
		    s->file_off > available || s->file_size > available - s->file_off ||
		    ((s->file_size + 7) & ~7ULL) > available - s->file_off)
			return "bad segment source";
		uint64_t off = s->vmaddr - p->virt_base;
		if (off > kernel_off || s->vmsize > kernel_off - off ||
		    s->file_size > s->vmsize ||
		    ((s->file_size + 7) & ~7ULL) > s->vmsize)
			return "bad segment target";
	}
	return 0;
}

const char *loader_boot(uintptr_t dtb)
{
#ifdef RAIN
	(void)dtb;
#endif
	uint64_t rd_start, rd_end;
	uintptr_t emb = ((uintptr_t)_end + 0xfff) & ~0xfffUL;

	/* The ARM64 Image header carries the true byte length, including any
	 * payload appended by build.sh. Never probe beyond that allocation. */
	uint64_t image_size = *(volatile const uint64_t *)((uintptr_t)_head + 16);
	if (image_size < (uintptr_t)_end - (uintptr_t)_head ||
	    image_size > MAX_IMAGE_SIZE)
		return "bad shim Image size";
	uintptr_t image_end = (uintptr_t)_head + image_size;
	if (image_end < (uintptr_t)_head)
		return "shim Image overflow";
	if (emb <= image_end && image_end - emb >= 8 && magic_ok((const char *)emb)) {
		rd_start = emb;
		rd_end = image_end;
		con_hex("EMBED", emb);
	} else {
#ifdef RAIN
		return "no SWEETXNU payload";
#else
		if (!fdt_chosen_u64(dtb, "linux,initrd-start", &rd_start) ||
		    !fdt_chosen_u64(dtb, "linux,initrd-end", &rd_end))
			return "no initrd in /chosen";
		if (rd_end <= rd_start || rd_end - rd_start > MAX_IMAGE_SIZE)
			return "bad initrd bounds";
		con_hex2("INITRD", "lo=", rd_start, "hi=", rd_end);
#endif
	}

	/*
	 * Boot image v4 (topaz ABL ignores v1/v2): ABL concatenates the
	 * vendor_boot ramdisk(s) and ours, so the payload is somewhere inside
	 * the initrd and not necessarily 8-byte aligned. Find it and move it
	 * down to an aligned address; the vendor ramdisk below it is unused.
	 */
	uintptr_t hit = 0;
	for (uintptr_t a = rd_start; a + 8 <= rd_end; a++)
		if (magic_ok((const char *)a)) {
			hit = a;
			break;
		}
	if (!hit)
		return "no SWEETXNU payload";
	if (hit != rd_start) {
		uintptr_t dst = (rd_start + 7) & ~7UL;
		volatile uint8_t *d = (volatile uint8_t *)dst;
		volatile const uint8_t *src = (volatile const uint8_t *)hit;

		con_hex2("PAYLOAD", "at=", hit, "to=", dst);
		for (uint64_t i = 0; i < rd_end - hit; i++)
			d[i] = src[i];
		rd_end = dst + (rd_end - hit);
		rd_start = dst;
	}
	if (rd_start & 7)
		return "unaligned payload";
	const struct payload *p = (const struct payload *)rd_start;
	const char *invalid = validate_payload(p, rd_end - rd_start);
	if (invalid)
		return invalid;

#ifdef RAIN
	/*
	 * The RAM window is chosen by the host tools (tools/mkadt.py). The
	 * kernel is copied to phys_base while this Image and the payload it
	 * carries are still in RAM, so the window has to start above them. It
	 * must also stay below the region Android reserves at the top of the
	 * upper bank (0xf3c00000-0xffbfffff in the live /proc/iomem); the
	 * tools keep 60 MiB of headroom below that.
	 *
	 * The base has to be aligned to the 32 MB twig that xnu's physical
	 * aperture slides on (arm_vm_physmap_slide): a base that is only
	 * 16 MB aligned hangs the kernel before it draws anything.
	 */
	if (p->phys_base < image_end || p->mem_size < 0x40000000ULL ||
	    p->phys_base + p->mem_size > RAIN_WINDOW_MAX_END ||
	    (p->phys_base & (RAIN_WINDOW_TWIG - 1)) != 0)
		return "wrong Rain RAM window";
#endif

	uint64_t pa_of_va_base = p->phys_base - p->virt_base;	/* pa = va + this */
	con_hex2("PHYS", "base=", p->phys_base, "size=", p->mem_size);
	con_hex("VIRT", p->virt_base);
	con_hex("ENTRY", p->entry_va);

	/* The payload must not overlap where the kernel goes. */
	if (rd_end > p->phys_base && rd_start < p->phys_base + p->mem_size)
		return "ramdisk overlaps kernel memory";

	for (uint32_t i = 0; i < p->nsegs; i++) {
		const struct payload_seg *s = &p->segs[i];
		uintptr_t dst = p->phys_base + (s->vmaddr - p->virt_base);
		copy64(dst, rd_start + s->file_off, s->file_size);
		if (s->vmsize > s->file_size)
			zero64(dst + ((s->file_size + 7) & ~7UL), s->vmsize - ((s->file_size + 7) & ~7UL));
	}
	con_hex2("SEGS", "n=", p->nsegs, "end=", p->kernel_end + pa_of_va_base);

	/* ADT, then boot_args, behind the kernel; everything below topOfKernelData is ours. */
	uintptr_t adt_pa = p->phys_base + (p->kernel_end - p->virt_base);
	copy64(adt_pa, rd_start + p->adt_off, p->adt_size);
	uintptr_t ba_pa = (adt_pa + p->adt_size + PAGE_16K - 1) & ~(PAGE_16K - 1);
	uintptr_t top = ba_pa + PAGE_16K;

	zero64(ba_pa, PAGE_16K);
	volatile struct boot_args *ba = (volatile struct boot_args *)ba_pa;
	ba->Revision = 2;
	ba->Version = 2;
	ba->virtBase = p->virt_base;
	ba->physBase = p->phys_base;
	ba->memSize = p->mem_size;
	ba->topOfKernelData = top;
	ba->Video.v_baseAddr = FB_BASE;
	ba->Video.v_display = 1;
	ba->Video.v_rowBytes = FB_STRIDE;
	ba->Video.v_width = FB_W;
	ba->Video.v_height = FB_H;
	ba->Video.v_depth = 32;
	ba->deviceTreeP = adt_pa - pa_of_va_base;	/* xnu reads it with the MMU on: a VA */
	ba->deviceTreeLength = (uint32_t)p->adt_size;
	for (int i = 0; i < BOOT_LINE_LENGTH; i++)
		ba->CommandLine[i] = p->cmdline[i];
	ba->memSizeActual = p->mem_size;
	con_hex2("BOOTARG", "pa=", ba_pa, "top=", top);

	uintptr_t entry_pa = p->phys_base + (p->entry_va - p->virt_base);
	con_hex("JUMP", entry_pa);
	con_str("XNU", "jumping (fbcon clears screen)");

	/* Everything was written with the MMU and caches off; drop any stale I-cache lines too. */
	__asm__ volatile("dsb sy; ic iallu; dsb sy; isb" ::: "memory");
	((xnu_entry_t)entry_pa)(ba_pa);
	return "xnu returned";
}
