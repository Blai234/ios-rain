"""Check the Rain touch driver's C syntax and types on the host.

The driver is a kernel file, so it cannot be compiled with the real XNU
headers outside a kernel build. This harness replaces the headers with
stubs (xnu_stubs.h) and compiles the driver as a userspace program, which
catches syntax errors, wrong argument counts and type mistakes before a
CI kernel build is spent on them.
"""
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PATCH = ROOT / 'xnu' / 'patches' / '0082-zrain-zz-fts-touch.patch'
STUBS = Path(__file__).resolve().parent / 'xnu_stubs.h'
CLANG = shutil.which('clang') or r'C:\Program Files\LLVM\bin\clang.exe'


def driver_source():
    """The new file as the patch adds it."""
    lines = []
    inside = False
    for line in PATCH.read_text(encoding='utf-8').splitlines():
        if line.startswith('+++ b/bsd/dev/sweet_fts.c'):
            inside = True
            continue
        if inside and line.startswith('--- '):
            break
        if inside and line.startswith('+') and not line.startswith('+++'):
            lines.append(line[1:])
    return '\n'.join(lines) + '\n'


def main():
    if not PATCH.is_file():
        print('touch patch missing')
        return 1
    if not Path(CLANG).is_file():
        print('no host clang; skipping')
        return 0
    source = driver_source()
    if 'rain_touch_init' not in source:
        print('the patch does not add the driver')
        return 1
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        (tmp / 'xnu_stubs.h').write_text(STUBS.read_text(encoding='utf-8'), encoding='utf-8')
        # The XNU headers the driver includes, reduced to the stubs.
        for header in ('sys/param.h', 'sys/systm.h', 'sys/errno.h', 'kern/clock.h',
                       'kern/thread.h', 'kern/sched_prim.h', 'machine/machine_routines.h',
                       'pexpert/pexpert.h', 'arm/caches_internal.h', 'vm/pmap.h',
                       'vm/vm_kern.h'):
            path = tmp / header
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text('#include "xnu_stubs.h"\n', encoding='utf-8')
        (tmp / 'sweet_fts.c').write_text(source, encoding='utf-8')
        # The driver is wrapped in the board config guard: define it so the
        # body is actually parsed.
        (tmp / 'wrap.c').write_text(
            '#define ARM64_BOARD_CONFIG_SWEET 1\n'
            '#include "sweet_fts.c"\n', encoding='utf-8')
        result = subprocess.run(
            [CLANG, '-fsyntax-only', '-std=gnu11', '-Wall', '-Wextra',
             '-Werror', '-I', str(tmp), str(tmp / 'wrap.c')],
            capture_output=True, text=True)
        if result.returncode:
            print(result.stdout + result.stderr)
            return 1
        print(f'RAIN FTS: the driver parses cleanly ({len(source.splitlines())} lines)')
    return 0


if __name__ == '__main__':
    sys.exit(main())
