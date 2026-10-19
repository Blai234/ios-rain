#!/usr/bin/env python3
"""Adapt the two inherited early-framebuffer diffs before the Rain XNU build.

Both patches are rewritten together so patch 0012's context matches the Rain
version of patch 0010. Their topology and hunk line counts stay unchanged.
"""
import argparse
from pathlib import Path

EARLY_PATCHES = ('0010-', '0012-')
REPLACEMENTS = (
    ('0x9c000000', '0x5c000000'),
    ('2368 * 4320', '1618 * 2880'),
    ('#4320', '#2880'),
    ('EARLY_WIDTH 1080u', 'EARLY_WIDTH 720u'),
    ('EARLY_HEIGHT 2400u', 'EARLY_HEIGHT 1650u'),
    ('4320u / 4', '2880u / 4'),
    ('stage * 64; x < (stage + 1) * 64',
     'stage * 32; x < (stage + 1) * 32'),
    ('stage * 48; x < (stage + 1) * 48',
     'stage * 32; x < (stage + 1) * 32'),
)


def rewrite(name, source):
    if not name.startswith(EARLY_PATCHES):
        return source
    result = source
    for old, new in REPLACEMENTS:
        if old in result:
            result = result.replace(old, new)
    if '0x9c000000' in result or 'EARLY_WIDTH 1080u' in result or 'EARLY_HEIGHT 2400u' in result:
        raise ValueError(f'{name}: Topaz framebuffer constants remain')
    if not all(x in result for x in ('0x5c000000', 'EARLY_WIDTH 720u',
                                    'EARLY_HEIGHT 1650u', '2880u / 4')):
        raise ValueError(f'{name}: expected Rain framebuffer constants missing')
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', type=Path)
    parser.add_argument('destination', type=Path)
    args = parser.parse_args()
    patched = rewrite(args.source.name, args.source.read_text(encoding='utf-8'))
    args.destination.write_text(patched, encoding='utf-8', newline='\n')


if __name__ == '__main__':
    main()
