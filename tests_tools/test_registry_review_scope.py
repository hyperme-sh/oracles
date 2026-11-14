"""Reject unintended registry/repository pairs before invoking any registry client."""
import os
from pathlib import Path
import subprocess

import pytest


@pytest.mark.parametrize('registry,repository', [
    ('ghcr.io','unrelated/private'), ('example.invalid','oracles'),
    ('https://example.azurecr.io','oracles'), ('example.azurecr.io','another'),
    ('example.azurecr.io/path','oracles'), ('example.azurecr.io.invalid','oracles'),
])
def test_unreviewed_registry_scope_fails_before_docker(tmp_path, registry, repository):
    docker=tmp_path/'docker'
    docker.write_text('#!/bin/sh\necho unexpected-docker-call\nexit 99\n');docker.chmod(0o755)
    env={**os.environ,'HISTORICAL_REGISTRY':registry,'HISTORICAL_REPOSITORY':repository,
         'PATH':str(tmp_path)+':'+os.environ['PATH']}
    result=subprocess.run(['bash',str(Path(__file__).parents[1]/'scripts/check-older-image.sh'),'sha256:'+'a'*64],
                          env=env,text=True,capture_output=True)
    assert result.returncode!=0
    assert 'unexpected-docker-call' not in result.stdout+result.stderr


def test_acr_copy_consumes_scoped_bearer_without_docker_login(tmp_path):
    skopeo=tmp_path/'skopeo';skopeo.write_text('#!/bin/sh\nprintf "%s\\n" "$@"\nexit 99\n');skopeo.chmod(0o755)
    docker=tmp_path/'docker';docker.write_text('#!/bin/sh\necho "$1" >> "$CALLS"\n');docker.chmod(0o755)
    calls=tmp_path/'calls'
    env={**os.environ,'HISTORICAL_REGISTRY':'example.azurecr.io','HISTORICAL_REPOSITORY':'oracles',
         'REGISTRY_TOKEN':'synthetic-scoped-bearer','CALLS':str(calls),'PATH':str(tmp_path)+':'+os.environ['PATH']}
    result=subprocess.run(['bash',str(Path(__file__).parents[1]/'scripts/check-older-image.sh'),'sha256:'+'a'*64],
                          env=env,text=True,capture_output=True)
    assert result.returncode==99
    assert '--src-registry-token\nsynthetic-scoped-bearer' in result.stdout
    assert 'docker-archive:' in result.stdout
    assert calls.read_text().splitlines()==['image']  # cleanup only
