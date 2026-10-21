/* Minimal stand-ins for the XNU headers the Rain touch driver uses, so the
 * driver can be parsed and type checked on the host.
 *
 * The kernel is LP64: vm_offset_t is 64 bit there, and the host's
 * "unsigned long" is 32 bit, so the type is spelled out here.
 */
#ifndef RAIN_FTS_STUBS_H
#define RAIN_FTS_STUBS_H

#include <stdint.h>
#include <stdbool.h>
#include <stddef.h>
#include <string.h>
#include <stdio.h>
#include <errno.h>

typedef uint64_t vm_offset_t;
typedef uint64_t vm_size_t;
typedef int kern_return_t;
typedef int wait_result_t;
typedef int thread_t;

#define KERN_SUCCESS 0
#define NSEC_PER_MSEC 1000000ULL
#define THREAD_UNINT 1
#define THREAD_CONTINUE_NULL 2

#define __unused __attribute__((unused))
#define __improbable(x) (x)

vm_offset_t ml_io_map(vm_offset_t pa, vm_size_t len);
int PE_parse_boot_argn(const char *arg, void *p, int size);
void clock_interval_to_deadline(unsigned ms, unsigned long long scale, uint64_t *deadline);
int assert_wait_deadline(int *chan, int state, uint64_t deadline);
void thread_block(int state);
void delay(int ms);
int kernel_thread_start(void (*fn)(void *, wait_result_t), void *arg, thread_t *th);
void thread_deallocate(thread_t th);
void sweet_hid_touch(int finger, int down, int x, int y);

/* DMA memory and cache maintenance (vm/vm_kern.h, vm/pmap.h,
 * arm/caches_internal.h). */
typedef uint64_t addr64_t;
typedef uint32_t ppnum_t;
typedef int boolean_t;
typedef void *vm_map_t;
typedef void *pmap_t;
#define TRUE 1
#define FALSE 0
#define PAGE_MASK 0x3fffULL
#define KMA_DATA 0x1
#define KMA_ZERO 0x2
#define KMA_PERMANENT 0x4
#define VM_KERN_MEMORY_IOKIT 26
extern vm_map_t kernel_map;
extern pmap_t kernel_pmap;
kern_return_t kmem_alloc_contig(vm_map_t map, vm_offset_t *addrp, vm_size_t size,
    vm_offset_t mask, ppnum_t max_pnum, ppnum_t pnum_mask, int flags, int tag);
ppnum_t pmap_find_phys(pmap_t pmap, addr64_t va);
#define ptoa_64(pn) ((uint64_t)(pn) << 14)
void flush_dcache64(addr64_t addr, unsigned count, boolean_t phys);

#endif /* RAIN_FTS_STUBS_H */
