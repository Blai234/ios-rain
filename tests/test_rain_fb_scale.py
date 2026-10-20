"""Check the Rain display scaling arithmetic in the XNU patch.

The kernel resamples the presented iPhone X canvas (1125x2436) into the
Rain panel (720x1650). The arithmetic lives in
xnu/patches/0082-zrain-display-geometry.patch (iokit/Kernel/arm/SweetFbScale.h)
and has no IOKit dependencies, so it can be compiled and checked on the host.
"""
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PATCH = ROOT / 'xnu' / 'patches' / '0082-zrain-display-geometry.patch'
HEADER = 'iokit/Kernel/arm/SweetFbScale.h'

HARNESS = r'''
#include "SweetFbScale.h"
#include <stdio.h>

static int failures;

#define CHECK(cond) do { \
	if (!(cond)) { \
		printf("FAIL line %d: %s\n", __LINE__, #cond); \
		failures++; \
	} \
} while (0)

/* Walk every panel pixel and check the source index stays in the source rect. */
static int
walk(const struct sweet_fb_scale *sc, uint32_t src_w, uint32_t src_h)
{
	uint32_t accy = 0;
	int bad = 0;

	for (int32_t j = 0; j < sc->ph; j++) {
		uint32_t accx = 0;
		uint32_t sy = sweet_fb_scale_sy(sc, accy);
		if (sy < sc->sy || sy >= sc->sy + sc->ah || sy >= src_h) {
			bad++;
		}
		for (int32_t i = 0; i < sc->pw; i++) {
			uint32_t sx = sweet_fb_scale_sx(sc, accx);
			if (sx < sc->sx || sx >= sc->sx + sc->aw || sx >= src_w) {
				bad++;
			}
			accx += sc->xstep;
		}
		accy += sc->ystep;
	}
	return bad;
}

int
main(void)
{
	struct sweet_fb_scale sc;
	uint32_t accx, accy;

	/* Rain: the iPhone X canvas on a 720x1650 panel. */
	CHECK(sweet_fb_scale_setup(&sc, 0, 0, 1125, 2436, 0, 0, 1125, 2436,
	    720, 1650, 1125, 2436, 1125, 2436) == 1);
	CHECK(sc.px == 0 && sc.py == 0);
	CHECK(sc.pw == 720 && sc.ph == 1650);
	CHECK(sc.sx == 0 && sc.sy == 0);
	CHECK(sc.aw == 1125 && sc.ah == 2436);
	CHECK(walk(&sc, 1125, 2436) == 0);
	/* The panel centre reads the canvas centre (within the rounding of the
	 * 16.16 step). */
	accx = 360u * sc.xstep;
	accy = 825u * sc.ystep;
	CHECK(sweet_fb_scale_sx(&sc, accx) >= 561 && sweet_fb_scale_sx(&sc, accx) <= 563);
	CHECK(sweet_fb_scale_sy(&sc, accy) >= 1217 && sweet_fb_scale_sy(&sc, accy) <= 1219);
	/* The whole canvas is used, not a centre crop. */
	CHECK(sweet_fb_scale_sx(&sc, 0) == 0);
	CHECK(sweet_fb_scale_sy(&sc, 0) == 0);
	CHECK(sweet_fb_scale_sx(&sc, (719u * sc.xstep)) == 1123);
	CHECK(sweet_fb_scale_sy(&sc, (1649u * sc.ystep)) == 2434);

	/* Identity: the presented size equals the panel size. */
	CHECK(sweet_fb_scale_setup(&sc, 0, 0, 1125, 2436, 0, 0, 1125, 2436,
	    1125, 2436, 1125, 2436, 1125, 2436) == 1);
	CHECK(sc.xstep == 65536 && sc.ystep == 65536);
	CHECK(sc.pw == 1125 && sc.ph == 2436);
	accx = 100u * sc.xstep;
	CHECK(sweet_fb_scale_sx(&sc, accx) == 100);
	CHECK(walk(&sc, 1125, 2436) == 0);

	/* A quarter of the canvas maps onto a quarter of the panel. */
	CHECK(sweet_fb_scale_setup(&sc, 0, 0, 562, 1218, 0, 0, 562, 1218,
	    720, 1650, 1125, 2436, 1125, 2436) == 1);
	CHECK(sc.pw == 359 && sc.ph == 825);
	CHECK(walk(&sc, 1125, 2436) == 0);

	/* A source rectangle inside the surface is honoured. */
	CHECK(sweet_fb_scale_setup(&sc, 0, 0, 1125, 2436, 100, 200, 500, 600,
	    720, 1650, 1125, 2436, 1125, 2436) == 1);
	CHECK(sc.sx == 100 && sc.sy == 200);
	CHECK(sc.aw == 500 && sc.ah == 600);
	CHECK(walk(&sc, 1125, 2436) == 0);

	/* A source rectangle that runs past the surface is clipped. */
	CHECK(sweet_fb_scale_setup(&sc, 0, 0, 1125, 2436, 1000, 2000, 4000, 4000,
	    720, 1650, 1125, 2436, 1125, 2436) == 1);
	CHECK(sc.aw == 125 && sc.ah == 436);
	CHECK(walk(&sc, 1125, 2436) == 0);

	/* Degenerate rectangles draw nothing. */
	CHECK(sweet_fb_scale_setup(&sc, 0, 0, 0, 2436, 0, 0, 1125, 2436,
	    720, 1650, 1125, 2436, 1125, 2436) == 0);
	CHECK(sweet_fb_scale_setup(&sc, 0, 0, 1125, 0, 0, 0, 1125, 2436,
	    720, 1650, 1125, 2436, 1125, 2436) == 0);
	CHECK(sweet_fb_scale_setup(&sc, 0, 0, 1125, 2436, 0, 0, 1125, 2436,
	    0, 1650, 1125, 2436, 1125, 2436) == 0);
	CHECK(sweet_fb_scale_setup(&sc, 0, 0, 1125, 2436, 0, 0, 1125, 2436,
	    720, 1650, 0, 2436, 1125, 2436) == 0);
	/* A destination rectangle outside the panel draws nothing. */
	CHECK(sweet_fb_scale_setup(&sc, 2000, 0, 1125, 2436, 0, 0, 1125, 2436,
	    720, 1650, 1125, 2436, 1125, 2436) == 0);

	if (failures == 0) {
		printf("RAIN FB SCALE OK\n");
		return 0;
	}
	printf("RAIN FB SCALE FAILURES: %d\n", failures);
	return 1;
}
'''


def compiler():
    """A host C++ compiler, or None."""
    for name in ('clang++', 'g++', 'c++'):
        found = shutil.which(name)
        if found:
            return found
    if os.name == 'nt':
        candidate = Path(os.environ.get('ProgramFiles', 'C:/Program Files')) / 'LLVM' / 'bin' / 'clang++.exe'
        if candidate.is_file():
            return str(candidate)
    return None


def extract_header(patch):
    """The new-file section of the patch, as the file the kernel compiles."""
    lines = patch.read_text(encoding='utf-8').splitlines()
    out = []
    inside = False
    for line in lines:
        if line.startswith('+++ b/'):
            inside = line[len('+++ b/'):].strip() == HEADER
            continue
        if line.startswith('--- ') or line.startswith('diff '):
            if line.startswith('--- '):
                inside = False
            continue
        if not inside:
            continue
        if line.startswith('@@'):
            continue
        if line.startswith('+'):
            out.append(line[1:])
        elif line.startswith(' '):
            out.append(line[1:])
        elif line.startswith('\\'):
            continue
    return '\n'.join(out) + '\n'


class RainFbScaleTest(unittest.TestCase):
    def setUp(self):
        self.patch = PATCH
        if not self.patch.is_file():
            self.skipTest('display geometry patch missing')

    def test_patch_contains_the_scaling_header(self):
        header = extract_header(self.patch)
        self.assertIn('sweet_fb_scale_setup', header)
        self.assertIn('struct sweet_fb_scale', header)

    def test_scaling_arithmetic(self):
        cc = compiler()
        if cc is None:
            self.skipTest('no host C++ compiler')
        with tempfile.TemporaryDirectory() as tmp:
            tmp = Path(tmp)
            (tmp / 'SweetFbScale.h').write_text(extract_header(self.patch), encoding='utf-8')
            (tmp / 'harness.cpp').write_text(HARNESS, encoding='utf-8')
            binary = tmp / ('harness.exe' if os.name == 'nt' else 'harness')
            subprocess.run([cc, '-std=c++17', '-O2', '-Wall', '-Wextra', '-Werror',
                            str(tmp / 'harness.cpp'), '-o', str(binary)], check=True)
            run = subprocess.run([str(binary)], capture_output=True, text=True)
            self.assertEqual(run.returncode, 0, run.stdout + run.stderr)
            self.assertIn('RAIN FB SCALE OK', run.stdout)


if __name__ == '__main__':
    unittest.main()
