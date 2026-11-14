import hashlib
import importlib.util
import io
import json
from pathlib import Path
import sys
import tarfile
import zipfile
import subprocess

import pytest

SCRIPTS = Path(__file__).resolve().parents[1] / 'scripts'
sys.path.insert(0, str(SCRIPTS))
import inventory_registry as registry
import review_image
import distribution_audit as audit


def test_registry_inventory_paginates_deduplicates_and_reports_other_platforms():
    amd = 'sha256:' + 'a' * 64
    arm = 'sha256:' + 'b' * 64
    document = {'manifests': [
        {'digest': amd, 'platform': {'os': 'linux', 'architecture': 'amd64'}},
        {'digest': arm, 'platform': {'os': 'linux', 'architecture': 'arm64'}}]}
    raw = json.dumps(document).encode(); digest = 'sha256:' + hashlib.sha256(raw).hexdigest()
    def request(url):
        if 'tags/list?n=100' in url:
            return {'tags': ['test']}, {'Link': '</v2/hyperme-sh/oracles/runtime/tags/list?last=test>; rel="next"'}, b''
        if 'tags/list?last=' in url:
            return {'tags': ['sha-old']}, {}, b''
        return document, {'Docker-Content-Digest': digest}, raw
    result = registry.inventory(request)
    assert result['images'] == [{'digest': amd, 'tags': ['sha-old', 'test']}]
    assert len(result['tag_observations']) == 2
    assert result['omitted_platform_manifests'][0]['digest'] == arm


@pytest.mark.parametrize('url', ['https://other.invalid/v2/hyperme-sh/oracles/runtime/tags/list',
    'http://ghcr.io/v2/hyperme-sh/oracles/runtime/tags/list',
    'https://ghcr.io/v2/another/repo/tags/list', 'https://user:secret@ghcr.io/v2/hyperme-sh/oracles/runtime/tags/list'])
def test_registry_credentials_cannot_follow_pagination_elsewhere(url):
    with pytest.raises(ValueError):registry.registry_url(url)


def test_registry_rejects_changed_manifest_bytes():
    def request(url):
        if 'tags/list' in url:return {'tags':['test']}, {}, b''
        return {}, {'Docker-Content-Digest':'sha256:'+'0'*64}, b'{}'
    with pytest.raises(ValueError, match='bytes'):registry.inventory(request)


def test_historical_layer_reports_hosted_code_and_metadata_without_execution(tmp_path):
    package=tmp_path/'1/opt/runtime/lib/python3.13/site-packages'
    target=package/'api/usecases/billing_service.py';target.parent.mkdir(parents=True)
    target.write_text('raise RuntimeError("must never execute")\n')
    metadata=package/'example.dist-info/METADATA';metadata.parent.mkdir()
    metadata.write_text('Name: example\nVersion: 1.0\n')
    report=review_image.inspect_layers(tmp_path)
    assert report['findings'][0]['kind']=='hosted-code'
    assert report['findings'][0]['sha256']==hashlib.sha256(target.read_bytes()).hexdigest()
    assert report['observed_layer_metadata'][0]['name']=='example'
    assert not report['observed_layer_metadata'][0]['declares_license']


def test_historical_classification_is_bound_to_member_bytes(tmp_path):
    import review_history
    directory = tmp_path/'.github/workflows'; directory.mkdir(parents=True)
    row = {'object':'object', 'member':'module.py', 'sha256':'a'*64, 'classification':'provider-adapter'}
    (directory/'historical-source-findings.json').write_text(json.dumps({'findings':[row]}))
    finding = dict(row); del finding['classification']
    assert review_history.classify_findings(tmp_path, [finding])['reviewed'] == 1
    assert finding['classification'] == 'provider-adapter'
    finding['sha256'] = 'b'*64
    with pytest.raises(ValueError, match='bytes differ'):
        review_history.classify_findings(tmp_path, [finding])
    assert review_history.classify_findings(tmp_path, [{'object':'new', 'member':'module.py'}])['unclassified'] == 1



def test_authenticated_registry_api_refuses_redirects():
    with pytest.raises(ValueError, match='redirects'):
        registry.NoRedirects().redirect_request(None, None, 302, 'Found', {}, 'https://other.invalid')


def test_historical_root_user_is_reported_but_current_image_policy_stays_strict(tmp_path):
    layer = io.BytesIO()
    with tarfile.open(fileobj=layer, mode='w'):
        pass
    archive = tmp_path/'image.tar'
    files = {'manifest.json': json.dumps([{'Config':'config.json','Layers':['layer.tar']}]).encode(),
             'config.json': b'{"config": {"User": "root"}}', 'layer.tar': layer.getvalue()}
    with tarfile.open(archive, 'w') as tar:
        for name, data in files.items():
            member = tarfile.TarInfo(name); member.size = len(data);tar.addfile(member, io.BytesIO(data))
    with pytest.raises(ValueError, match='unprivileged'):
        audit.unpack_image(archive, tmp_path/'strict')
    assert audit.unpack_image(archive, tmp_path/'historical', require_unprivileged=False)['user']=='root'


@pytest.mark.parametrize('change', ['none', 'bytes', 'path', 'line', 'rule'])
def test_public_file_classification_requires_exact_upstream_bytes_and_coordinates(tmp_path, change):
    from classify_historical_findings import classify_public_files
    path = tmp_path/'1/opt/runtime/share/map.js';path.parent.mkdir(parents=True)
    path.write_bytes(b'public source map')
    records={'files':[{'path':'opt/runtime/share/map.js','sha256':hashlib.sha256(path.read_bytes()).hexdigest(),
                      'rules':{'generic-api-key':[6]}}]}
    finding={'File':str(path),'StartLine':6,'RuleID':'generic-api-key'}
    if change=='bytes':path.write_bytes(b'changed')
    if change=='path':finding['File']=str(tmp_path/'1/opt/runtime/private.txt')
    if change=='line':finding['StartLine']=7
    if change=='rule':finding['RuleID']='private-key'
    accepted, unexpected=classify_public_files([finding],tmp_path,records)
    assert accepted==(1 if change=='none' else 0)
    assert unexpected==([] if change=='none' else [finding])


@pytest.mark.parametrize('change', ['none', 'bytes', 'path', 'line', 'rule'])
def test_committed_archived_map_classification(tmp_path, monkeypatch, change):
    from pathlib import Path
    from types import SimpleNamespace
    from classify_historical_findings import classify_public_files
    records = json.loads((Path(__file__).resolve().parents[1] /
                          '.github/workflows/historical-public-files.json').read_text())
    relative = 'app/.venv/share/jupyter/nbextensions/pydeck/index.js.map'
    row = next(item for item in records['files'] if item['path'] == relative)
    expected = '1ef6c893f0577fdbe521570ecd9a94526cc982cdf46b6d85c9e5236d792811ba'
    assert row['sha256'] == expected
    assert row['rules'] == {'generic-api-key': [6]}
    assert row['version'] == '0.9.3'
    # Stub the 19 MB upstream member's digest, not configuration or matching.
    # CI checks the actual retained image bytes against the committed hash.
    sentinel = b'unit-only upstream member stand-in'
    def digest(stream, algorithm):
        assert algorithm == 'sha256'
        data = stream.read()
        value = expected if data == sentinel else hashlib.sha256(data).hexdigest()
        return SimpleNamespace(hexdigest=lambda: value)
    monkeypatch.setattr(hashlib, 'file_digest', digest)
    path = tmp_path/'5'/relative
    path.parent.mkdir(parents=True)
    path.write_bytes(sentinel if change != 'bytes' else b'changed member')
    finding = {'File': str(path), 'StartLine': 6, 'RuleID': 'generic-api-key'}
    if change == 'path': finding['File'] = str(path.with_name('private.js.map'))
    if change == 'line': finding['StartLine'] = 7
    if change == 'rule': finding['RuleID'] = 'private-key'
    accepted, unexpected = classify_public_files([finding], tmp_path, records)
    assert accepted == (1 if change == 'none' else 0)
    assert unexpected == ([] if change == 'none' else [finding])
