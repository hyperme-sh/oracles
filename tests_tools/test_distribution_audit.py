import importlib.util
import io
import json
from pathlib import Path
import tarfile
import pytest

spec=importlib.util.spec_from_file_location('audit',Path(__file__).parents[1]/'scripts/distribution_audit.py')
audit=importlib.util.module_from_spec(spec);spec.loader.exec_module(audit)


def test_current_lock_has_exact_reviewed_git_owners():
    assert len(audit.git_inventory(Path(__file__).parents[1]))==7


@pytest.mark.parametrize('path,content',[
    ('src/oracles_service/.env','x=y'),
    ('src/oracles_service/private-rules/policy.py','x=1'),
    ('src/oracles_service/payment_service.py','x=1'),
    ('src/oracles_service/x.py','from stripe import Charge'),
    ('src/oracles_service/x.py','HOST="private-host.ts.net"'),
])
def test_private_content_is_rejected(tmp_path,path,content):
    target=tmp_path/path;target.parent.mkdir(parents=True);target.write_text(content)
    with pytest.raises(ValueError):audit.check_tree(tmp_path,source=True)


def test_unresolved_license_is_reported_without_inventing_terms(tmp_path,monkeypatch):
    (tmp_path/'AGENTS.md').write_text('Contributor guidance')
    monkeypatch.setattr(audit,'git_inventory',lambda root:[])
    result=audit.source_audit(tmp_path)
    assert result['owner_license']=='unresolved' and result['owner_notice']=='unresolved'
    assert result['publication_authorized'] is False


def tar_bytes(files):
    buf=io.BytesIO()
    with tarfile.open(fileobj=buf,mode='w') as archive:
        for name,value in files.items():
            info=tarfile.TarInfo(name);info.size=len(value);archive.addfile(info,io.BytesIO(value))
    return buf.getvalue()


def test_each_layer_is_scanned_even_if_later_layer_deletes_file(tmp_path):
    archive=tmp_path/'image.tar'
    archive.write_bytes(tar_bytes({'manifest.json':json.dumps([{'Config':'config.json','Layers':['a.tar','b.tar']}]).encode(),
        'config.json':b'{"config":{"User":"65532:65532"}}',
        'a.tar':tar_bytes({'app/.env':b'test-only=value'}),
        'b.tar':tar_bytes({'app/.wh..env':b''})}))
    root=tmp_path/'layers';audit.unpack_image(archive,root)
    with pytest.raises(ValueError):audit.check_tree(root/'0'/'app')


def test_layer_traversal_is_rejected(tmp_path):
    archive=tmp_path/'image.tar'
    archive.write_bytes(tar_bytes({'manifest.json':b'[{"Config":"c","Layers":["a"]}]',
        'c':b'{"config":{"User":"65532:65532"}}','a':tar_bytes({'../outside':b'bad'})}))
    with pytest.raises(ValueError,match='Unsafe'):audit.unpack_image(archive,tmp_path/'layers')


def test_plain_dpkg_record_keeps_its_bytes_for_secret_scanning(tmp_path):
    path=tmp_path/'builtins.7.gz';path.write_bytes(b'plain alternatives metadata')
    audit.normalize_scan_names(tmp_path)
    assert (tmp_path/'builtins.7.gz.scan-text').read_bytes()==b'plain alternatives metadata'
    compressed=tmp_path/'real.gz';compressed.write_bytes(b'\x1f\x8brest')
    audit.normalize_scan_names(tmp_path)
    assert compressed.is_file()


def test_runtime_image_bytes_must_match_committed_source(tmp_path,monkeypatch):
    from types import SimpleNamespace
    source=tmp_path/'src';installed=tmp_path/'installed'
    (source/'oracles_service').mkdir(parents=True);installed.mkdir()
    (source/'oracles_service/app.py').write_text('x=1')
    (installed/'app.py').write_text('x=1')
    monkeypatch.setattr(audit.importlib.metadata,'distribution',lambda name:SimpleNamespace(locate_file=lambda path:installed))
    audit.verify_runtime_source(source)
    (installed/'app.py').write_text('x=2')
    with pytest.raises(ValueError,match='differs'):audit.verify_runtime_source(source)


@pytest.mark.parametrize('failure', ['missing', 'changed', 'empty'])
def test_owner_notices_reject_missing_changed_or_empty_text(tmp_path, failure):
    source = tmp_path / 'source'; source.mkdir()
    installed = tmp_path / 'installed'; installed.mkdir()
    for name in ('LICENSE', 'NOTICE'):
        (source / name).write_text(name)
        (installed / name).write_text(name)
    audit.verify_owner_notices(source, installed)
    if failure == 'missing':
        (installed / 'NOTICE').unlink()
    elif failure == 'changed':
        (installed / 'NOTICE').write_text('changed')
    else:
        (source / 'NOTICE').write_text('')
        (installed / 'NOTICE').write_text('')
    with pytest.raises((ValueError, FileNotFoundError)):
        audit.verify_owner_notices(source, installed)


def test_final_image_notice_inventory_and_bytes_are_verified(tmp_path):
    import hashlib
    (tmp_path / 'LICENSE').write_text('owner terms')
    (tmp_path / 'NOTICE').write_text('owner attribution')
    directory = tmp_path / 'third-party/example'
    directory.mkdir(parents=True)
    (directory / 'LICENSE').write_bytes(b'upstream terms')
    rows = [{'name': 'example', 'version': '1.0', 'texts': {
        'LICENSE': {'file': 'LICENSE', 'sha256': hashlib.sha256(b'upstream terms').hexdigest()}}}]
    (tmp_path / 'third-party/index.json').write_text(json.dumps(rows))
    audit.verify_notice_bundle(tmp_path, [{'name': 'example', 'version': '1.0'}])
    with pytest.raises(ValueError, match='inventory'):
        audit.verify_notice_bundle(tmp_path, [{'name': 'example', 'version': '2.0'}])
    (directory / 'LICENSE').write_bytes(b'altered terms')
    with pytest.raises(ValueError, match='bytes'):
        audit.verify_notice_bundle(tmp_path, [{'name': 'example', 'version': '1.0'}])
