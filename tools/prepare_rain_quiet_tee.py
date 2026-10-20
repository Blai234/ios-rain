#!/usr/bin/env python3
"""Prepare a one-variable Rain boot experiment from the verified payload."""
from pathlib import Path
import hashlib
import json

from validate_rain_payload import validate

root = Path(__file__).resolve().parents[1]
source = root / 'xnu/out-rain-ci/rain-nullfilter.payload'
target = root / 'xnu/out-rain-ci/rain-quiet-tee.payload'
original = source.read_bytes()
sha = lambda b: hashlib.sha256(b).hexdigest()
assert sha(original) == '41de0e0ea0d2483896ece62d672c6663d91db19120db8bf16671b477d02ea31d'
start, end = 0x48, 0x2a8
old_line = original[start:end].split(b'\0', 1)[0].decode('ascii')
assert old_line.count('sweetnull=backboardd,SpringBoard') == 1
assert old_line.count('rainquietscaler=1') == 1
new_line = old_line.replace('sweetnull=backboardd,SpringBoard', 'sweetnull=SpringBoard')
assert all(x in new_line.split() for x in ('cpus=1', 'ufscow=1', 'rootrw=1',
                                          'rainseedmigration=1', 'rainquietscaler=1'))
assert not any(x.startswith('ufsrw') for x in new_line.split())
candidate = bytearray(original)
encoded = new_line.encode('ascii') + b'\0'
assert len(encoded) <= end - start
candidate[start:end] = encoded.ljust(end - start, b'\0')
candidate = bytes(candidate)
assert candidate[:start] == original[:start] and candidate[end:] == original[end:]
checks = validate(candidate, allow_volatile_ufs=True)
target.write_bytes(candidate)
report = dict(source=str(source), source_sha256=sha(original), candidate=str(target),
              candidate_sha256=sha(candidate), changed_region='boot command line only',
              old_command_line=old_line, new_command_line=new_line, preflight=checks)
(target.with_suffix('.json')).write_text(json.dumps(report, indent=2) + '\n')
print(json.dumps(report, indent=2))
