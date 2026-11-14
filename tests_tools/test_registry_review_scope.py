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
