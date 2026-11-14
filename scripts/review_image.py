"""Inspect historical image bytes and layer metadata without running their code."""
import argparse
from email.parser import BytesParser
import hashlib
import json
from pathlib import Path

from distribution_audit import check_member, unpack_image, normalize_scan_names, PRIVATE_PARTS, PRIVATE_VALUE


def inspect_layers(root):
    findings, metadata, legal = [], [], []
    for path in sorted(root.rglob('*')):
        if not path.is_file() or path.is_symlink():
            continue
        relative = path.relative_to(root).as_posix()
        name = relative.split('/site-packages/', 1)[-1]
        if PRIVATE_PARTS.intersection(path.relative_to(root).parts) or path.name in {'.env', 'id_rsa', 'id_ed25519'}:
            findings.append({'path': relative, 'kind': 'private-path'})
        if path.suffix in ('.py', '.json', '.toml', '.yaml', '.yml') or path.name == 'METADATA':
            data = path.read_bytes()
            try:
                check_member(name, data)
            except ValueError:
                findings.append({'path': relative, 'kind': 'hosted-code', 'sha256': hashlib.sha256(data).hexdigest()})
            if PRIVATE_VALUE.search(data.decode(errors='replace')):
                findings.append({'path': relative, 'kind': 'private-deployment-value', 'sha256': hashlib.sha256(data).hexdigest()})
        if path.name == 'METADATA' and '.dist-info/' in relative:
            record = BytesParser().parsebytes(path.read_bytes(), headersonly=True)
            metadata.append({'path': relative, 'name': record.get('Name'), 'version': record.get('Version'),
                             'license_expression': record.get('License-Expression'),
                             'declares_license': bool(record.get('License') or record.get('License-Expression'))})
        if '/usr/share/doc/oracles-service/' in '/' + relative:
            legal.append({'path': relative, 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()})
    return {'findings': findings, 'observed_layer_metadata': metadata, 'observed_legal_materials': legal,
            'limitations': 'All retained layers, including deleted files; layer observations are not a reconstructed final filesystem or license clearance'}


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('archive'); parser.add_argument('layers', type=Path); parser.add_argument('digest')
    args = parser.parse_args()
    result = unpack_image(args.archive, args.layers, require_unprivileged=False)
    result.update(inspect_layers(args.layers))
    result['digest'] = args.digest
    normalize_scan_names(args.layers)
    print('HISTORICAL_IMAGE_REVIEW=' + json.dumps(result, sort_keys=True))
