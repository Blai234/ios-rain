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

#endif /* RAIN_FTS_STUBS_H */
