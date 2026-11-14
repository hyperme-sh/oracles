"""Recognize exact public upstream files; leave every other finding visible."""
import argparse
import hashlib
import json
from pathlib import Path

from classify_source_findings import classify


def classify_public_files(findings, layers, records):
    known = {row['path']: row for row in records['files']}
    accepted, unexpected = 0, []
    hashes = {}
    for finding in findings:
        path = Path(finding['File']).resolve()
        try:
            relative = path.relative_to(layers.resolve())
        except ValueError:
            unexpected.append(finding); continue
        record = known.get('/'.join(relative.parts[1:]))
        if (not relative.parts or not relative.parts[0].isdigit() or not record
                or finding['StartLine'] not in record['rules'].get(finding['RuleID'], [])):
            unexpected.append(finding); continue
        if path not in hashes:
            with path.open('rb') as stream:
                hashes[path] = hashlib.file_digest(stream, 'sha256').hexdigest()
        if hashes[path] == record['sha256']:
            accepted += 1
        else:
            unexpected.append(finding)
    return accepted, unexpected


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('findings', type=Path); parser.add_argument('layers', type=Path)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    accepted, remaining = classify_public_files(json.loads(args.findings.read_text()), args.layers,
        json.loads((root/'.github/workflows/historical-public-files.json').read_text()))
    vectors, unexpected = classify(remaining, args.layers,
        json.loads((root/'licenses/sources.json').read_text()),
        json.loads((root/'.github/workflows/source-scan-baseline.json').read_text()))
    print(json.dumps({'known_public_file_findings': accepted, 'known_public_source_findings': vectors,
                      'unexpected_findings': len(unexpected)}))
    for finding in unexpected:
        print(json.dumps({key: finding.get(key) for key in ('File', 'StartLine', 'RuleID')}))
    raise SystemExit(1 if unexpected else 0)
