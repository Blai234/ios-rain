#!/usr/bin/env python3
"""Read selected live Rain device-tree nodes; omit serials and raw firmware blobs."""
import argparse
import io
import json
import re
import subprocess
import tarfile
from pathlib import Path

ROOT = '/sys/firmware/devicetree/base'
SUBTREES = (
    'soc/qcom,dsi-display-primary',
    'soc/qcom,mdss_mdp',
    'soc/spi@4a80000',
    'soc/i2c@4a88000',
    'soc/gpio_keys',
    'soc/xiaomi_touch',
    'soc/qcom,spmi@1c40000/qcom,pm6125@0/qcom,power-on@800',
    'soc/qcom,spmi@1c40000/qcom,pm6125@0/pinctrl@c000/key_vol_up',
)
PROP = re.compile(r'(status|compatible|panel.name|panel.width|panel.height|panel.framerate|panel.type|panel.id|'
                  r'pref.prim.pan|phandle|reg$|interrupt|irq|reset.gpio|gpio$|linux,code|'
                  r'display.name|display.type)', re.I)
PRIVATE = re.compile(r'(serial|mac.address|seed|hash|calibration|nvmem)', re.I)


def decode(raw):
    if not raw:
        return True
    parts = raw.rstrip(b'\0').split(b'\0')
    if all(parts) and all(32 <= b < 127 for part in parts for b in part):
        return [part.decode('ascii') for part in parts]
    if len(raw) <= 32 and len(raw) % 4 == 0:
        return [hex(int.from_bytes(raw[i:i + 4], 'big')) for i in range(0, len(raw), 4)]
    return {'bytes': len(raw)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--adb', required=True)
    parser.add_argument('--output', required=True, type=Path)
    args = parser.parse_args()
    command = 'tar -C ' + ROOT + ' -cf - ' + ' '.join(SUBTREES) + ' 2>/dev/null'
    result = subprocess.run([args.adb, 'exec-out', 'su', '-c', command],
                            capture_output=True, timeout=45, check=True)
    if len(result.stdout) > 10 * 1024 * 1024:
        raise RuntimeError('unexpectedly large device-tree selection')
    properties = {}
    with tarfile.open(fileobj=io.BytesIO(result.stdout)) as archive:
        for member in archive:
            if not member.isfile():
                continue
            parent, _, name = member.name.rpartition('/')
            if not PROP.search(name) or PRIVATE.search(name):
                continue
            raw = archive.extractfile(member).read()
            properties.setdefault(parent, {})[name] = decode(raw)

    interesting = {}
    for node, props in properties.items():
        if (node.startswith('soc/qcom,mdss_mdp/qcom,mdss_dsi_') and
                '/qcom,mdss-dsi-display-timings' not in node and
                node.count('/') == 2):
            interesting[node] = props
        elif node.startswith('soc/qcom,mdss_mdp/qcom,mdss_dsi_panel_c3q_43_03_0b_fhdp_video/'
                             'qcom,mdss-dsi-display-timings/timing@'):
            interesting[node] = props
        elif node.startswith(('soc/qcom,dsi-display-primary', 'soc/spi@4a80000/',
                              'soc/i2c@4a88000/', 'soc/gpio_keys/',
                              'soc/xiaomi_touch', 'soc/qcom,spmi@1c40000/')):
            interesting[node] = props
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(interesting, indent=2, sort_keys=True) + '\n',
                           encoding='utf-8')
    print(f'{len(interesting)} relevant nodes written to {args.output}')
    for node, props in interesting.items():
        if node.count('/') <= 2 and ('status' in props or 'qcom,dsi-pref-prim-pan' in props):
            print(node, 'status=', props.get('status'), 'compatible=', props.get('compatible'),
                  'preferred=', props.get('qcom,dsi-pref-prim-pan'))


if __name__ == '__main__':
    main()
