"""Static source/image checks and license inventory. Never publishes anything."""
import argparse
import hashlib
import ast
import importlib.metadata
import json
from pathlib import Path, PurePosixPath
import re
import tarfile
import tomllib
import warnings
from urllib.parse import urlsplit, parse_qs

PUBLIC_GIT = {
    'controlplane-api': 'hyperme-sh/controlplane-api',
    'controlplane-core': 'hyperme-sh/controlplane-core',
    'controlplane-db': 'hyperme-sh/controlplane-db',
    'controlplane-events': 'hyperme-sh/controlplane-events',
    'controlplane-identity': 'hyperme-sh/controlplane-identity',
    'controlplane-tenancy': 'hyperme-sh/controlplane-tenancy',
    'operator-ban-store': 'hyperme-sh/user-service',
}
FORBIDDEN_MODULES = ('controlplane_billing', 'payment_service', 'stripe', 'braintree', 'paypalrestsdk')
PRIVATE_PARTS = {'.git', '.aws', '.azure', '.ssh', 'private-rules', 'review-data', 'node_modules'}
PRIVATE_VALUE = re.compile(r'(?:acrfyber[a-z0-9]*\.azurecr\.io|[a-z0-9-]+\.privatelink\.[a-z0-9.-]+|[a-z0-9-]+\.ts\.net)', re.I)


def git_inventory(root):
    rows=[]
    for package in tomllib.loads((root/'uv.lock').read_text())['package']:
        source=package.get('source',{})
        if 'git' not in source:
            if any(k in source for k in ('directory','path')):
                raise ValueError('Unreviewed local dependency: '+package['name'])
            continue
        parsed=urlsplit(source['git']);repo=parsed.path.removesuffix('.git').strip('/')
        revision=parsed.fragment
        query=parse_qs(parsed.query)
        subdirectory={'operator-ban-store':'core/user-service/contracts',
            'controlplane-legacy-auth-bridge':'compatibility'}.get(package['name'])
        expected_query={'rev':[revision]}
        if subdirectory:expected_query['subdirectory']=[subdirectory]
        if (parsed.scheme!='https' or parsed.netloc!='github.com' or
            PUBLIC_GIT.get(package['name'])!=repo or not re.fullmatch('[0-9a-f]{40}',revision) or
            query!=expected_query):
            raise ValueError('Unreviewed Git dependency: '+package['name'])
        rows.append({'name':package['name'],'repository':repo,'revision':revision})
    if {r['name'] for r in rows}!=set(PUBLIC_GIT):
        raise ValueError('Locked Git dependency inventory changed')
    return rows


def check_tree(root, *, source=False):
    for path in root.rglob('*'):
        rel=path.relative_to(root)
        if PRIVATE_PARTS.intersection(rel.parts) or path.name in {'.env','id_rsa','id_ed25519'} or path.name.startswith('.env.'):
            raise ValueError('Private path in distribution: '+str(rel))
        if any(part.split('.')[0].replace('-','_') in FORBIDDEN_MODULES for part in rel.parts):
            raise ValueError('Hosted-only module in distribution: '+str(rel))
        if not path.is_file() or path.is_symlink():continue
        if path.suffix=='.py':
            with warnings.catch_warnings():
                warnings.simplefilter('ignore', SyntaxWarning)
                tree=ast.parse(path.read_text(errors='replace'))
            for node in ast.walk(tree):
                names=([a.name for a in node.names] if isinstance(node,ast.Import)
                       else [node.module or ''] if isinstance(node,ast.ImportFrom) else [])
                if any(name.split('.')[0] in FORBIDDEN_MODULES for name in names):
                    raise ValueError('Hosted-only import in '+str(rel))
        # Documentation may explain refusal examples; runtime must not embed deployment values.
        if path.suffix in {'.py','.json','.toml','.yaml','.yml'} and ('src' in rel.parts or not source):
            if PRIVATE_VALUE.search(path.read_text(errors='replace')):
                raise ValueError('Private deployment value in '+str(rel))


def source_audit(root):
    if not (root/'AGENTS.md').is_file():raise ValueError('Contributor guidance missing')
    check_tree(root,source=True)
    return {'git_dependencies':git_inventory(root),
            'owner_license': 'present' if (root/'LICENSE').is_file() else 'unresolved',
            'owner_notice': 'present' if (root/'NOTICE').is_file() else 'unresolved',
            'publication_authorized':False}


def unpack_image(archive, destination):
    # Inspect every final-image layer, including deleted lower-layer files.
    with tarfile.open(archive) as outer:
        manifest=json.load(outer.extractfile('manifest.json'))
        if len(manifest)!=1:raise ValueError('Expected one saved image')
        config=json.load(outer.extractfile(manifest[0]['Config']))
        if config.get('config',{}).get('User')!='65532:65532':raise ValueError('Runtime must be unprivileged')
        for i,name in enumerate(manifest[0]['Layers']):
            target=destination/str(i);target.mkdir(parents=True)
            with tarfile.open(fileobj=outer.extractfile(name)) as layer:
                members=[]
                for member in layer:
                    path=PurePosixPath(member.name)
                    if path.is_absolute() or '..' in path.parts:raise ValueError('Unsafe layer path')
                    # No links/devices are materialized; scan regular bytes in every layer.
                    if member.isfile() or member.isdir():members.append(member)
                layer.extractall(target,members=members,filter='data')
        (destination/"image-config.json").write_text(json.dumps(config,indent=2))
        return {"layers":len(manifest[0]["Layers"]),"user":config["config"]["User"]}


def normalize_scan_names(root):
    # dpkg alternatives records may end in .gz although their bytes are plain text.
    # Preserve all bytes but prevent extension-based archive decoding from skipping them.
    for path in root.rglob('*.gz'):
        if path.is_file() and not path.is_symlink():
            with path.open('rb') as stream:magic=stream.read(2)
            if magic!=b'\x1f\x8b':
                target=path.with_name(path.name+'.scan-text')
                if target.exists():raise ValueError('Scan path collision')
                path.rename(target)


def verify_runtime_source(source):
    installed=Path(importlib.metadata.distribution('oracles-service').locate_file('oracles_service'))
    def files(root):
        return {str(p.relative_to(root)):hashlib.sha256(p.read_bytes()).hexdigest()
                for p in root.rglob('*') if p.is_file() and '__pycache__' not in p.parts and p.suffix!='.pyc'}
    expected=files(source/'oracles_service')
    if not expected or files(installed)!=expected:raise ValueError('Image runtime differs from committed source')


def verify_owner_notices(source, installed=Path('/usr/share/doc/oracles-service')):
    for name in ('LICENSE', 'NOTICE'):
        expected = (source / name).read_bytes()
        if not expected.strip() or (installed / name).read_bytes() != expected:
            raise ValueError('Image owner legal text differs: ' + name)


def installed_inventory():
    rows=[]
    for dist in importlib.metadata.distributions():
        metadata=dist.metadata
        rows.append({'name':metadata['Name'],'version':dist.version,
            'license_expression':metadata.get('License-Expression'),
            'license':metadata.get('License'),
            'license_classifiers':[v for v in metadata.get_all('Classifier',[]) if v.startswith('License ::')],
            'license_files':[str(p) for p in dist.files or [] if any(x in str(p).lower() for x in ('license','notice','copying'))],
            'direct_url':json.loads(dist.read_text('direct_url.json') or 'null')})
    return sorted(rows,key=lambda row:row['name'].lower())


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('mode',choices=['source','image','installed'])
    parser.add_argument('--owner-source');parser.add_argument('path',nargs='?');parser.add_argument('--output');args=parser.parse_args()
    if args.mode=='source':result=source_audit(Path(args.path))
    elif args.mode=='image':
        root=Path(args.output);result=unpack_image(args.path,root)
        check_tree(root)
        normalize_scan_names(root)
    else:
        if args.path:verify_runtime_source(Path(args.path))
        if args.owner_source:verify_owner_notices(Path(args.owner_source))
        result=installed_inventory()
    print(json.dumps(result,sort_keys=True,indent=2))
