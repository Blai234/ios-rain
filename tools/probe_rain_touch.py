#!/usr/bin/env python3
"""Collect Rain touchscreen configuration over ADB without changing the device.

Works with root adbd in recovery or an Android shell with su. The full device
tree is parsed in memory; only touch nodes and their referenced configuration
nodes are saved. Device identifiers and calibration data are excluded.
"""
import argparse
import io
import json
import re
import subprocess
import tarfile
from pathlib import Path

from probe_rain_hardware import decode, PRIVATE

DT_ROOT = '/sys/firmware/devicetree/base'
COMMANDS = {
    'spi_driver': 'readlink -f /sys/bus/spi/devices/spi0.0/driver',
    'spi_modalias': 'cat /sys/bus/spi/devices/spi0.0/modalias',
    'input_capabilities': 'getevent -lp',
    'touch_log': 'dmesg',
    'clocks': 'cat /sys/kernel/debug/clk/clk_summary',
    'gpios': 'cat /sys/kernel/debug/gpio',
}
FILTERS = {
    'touch_log': re.compile(r'\b(?:fts|fts_ts|focaltech|spi_geni 4a80000)\b', re.I),
    'clocks': re.compile(r'qup|spi|serial', re.I),
    'gpios': re.compile(r'gpio-(80|86)\b|touch|fts|spi', re.I),
}
ANSI = re.compile(r'\x1b\[[0-9;]*m')


def shell(adb, command, root=False, binary=False):
    args = [adb, 'exec-out']
    args += ['su', '-c', command] if root else ['sh', '-c', command]
    result = subprocess.run(args, capture_output=True, timeout=45)
    if binary:
        if result.returncode:
            raise RuntimeError(result.stderr.decode(errors='replace'))
        return result.stdout
    return {'exit_code': result.returncode,
            'stdout': result.stdout.decode(errors='replace'),
            'stderr': result.stderr.decode(errors='replace')}


def selected_tree(blob):
    if len(blob) > 32 * 1024 * 1024:
        raise ValueError('device tree archive exceeds expected size')
    nodes = {}
    with tarfile.open(fileobj=io.BytesIO(blob)) as archive:
        for member in archive:
            if not member.isfile():
                continue
            name = member.name.removeprefix('./')
            parent, _, prop = name.rpartition('/')
            if PRIVATE.search(prop):
                continue
            raw = archive.extractfile(member).read()
            nodes.setdefault(parent, {})[prop] = raw
    handles = {}
    for node, props in nodes.items():
        for key in ('phandle', 'linux,phandle'):
            raw = props.get(key, b'')
            if len(raw) == 4:
                handles[int.from_bytes(raw, 'big')] = node
    chosen = {n for n in nodes if n in ('soc/spi@4a80000',
                                       'soc/spi@4a80000/novatek@0',
                                       'soc/xiaomi_touch')}
    # Follow only known reference properties; numeric register values are
    # not treated as phandles. Include descendants of referenced pin groups.
    for _ in range(3):
        expanded = set(chosen)
        for node in chosen:
            for key, raw in nodes[node].items():
                if not (key.startswith('pinctrl-') or key in
                        ('clocks', 'interrupt-parent', 'power-domains') or
                        key.endswith(('-gpio', '-gpios', '-supply'))):
                    continue
                if len(raw) % 4:
                    continue
                for i in range(0, len(raw), 4):
                    ref = handles.get(int.from_bytes(raw[i:i + 4], 'big'))
                    if ref:
                        expanded.add(ref)
                        if key.startswith('pinctrl-'):
                            expanded.update(n for n in nodes if n.startswith(ref + '/'))
        if expanded == chosen:
            break
        chosen = expanded
    return {n: {k: decode(v) for k, v in nodes[n].items()}
            for n in sorted(chosen)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--adb', required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    identity = shell(args.adb, 'id -u')
    use_su = identity['stdout'].strip() != '0'
    if use_su and shell(args.adb, 'id -u', root=True)['stdout'].strip() != '0':
        parser.error('root recovery ADB or Android su is required')
    archive = shell(args.adb, 'tar -C ' + DT_ROOT + ' -cf - .',
                    root=use_su, binary=True)
    report = {'device_tree': selected_tree(archive), 'observations': {}}
    for name, command in COMMANDS.items():
        result = shell(args.adb, command, root=use_su)
        if name in FILTERS:
            lines = (ANSI.sub('', line) for line in result['stdout'].splitlines())
            result['stdout'] = '\n'.join(line for line in lines
                                        if 'Kernel command line' not in line and
                                        FILTERS[name].search(line))
        report['observations'][name] = result
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + '\n', encoding='utf-8')
    print(f'Saved {len(report["device_tree"])} touch configuration nodes to {args.output}')


if __name__ == '__main__':
    main()
