from __future__ import annotations

import hashlib

import pytest

from oracles_service.auth import ATTEST_AUTH_REQUIRED, ATTEST_PURPOSE_REQUIRED
from oracles_service.settings import (
    AttestSubjectError,
    OraclesConfigError,
    load_oracles_settings,
    sanitize_subject,
)
from oracles_service.upstream import FetchResult, HttpAttestUpstream, MockAttestUpstream, sha256_digest

# Keep in sync with tests/conftest.py. Do not `from tests.conftest import …` —
# after `uv sync --all-packages` that name resolves to another workspace
# member's tests/ (CI: core/acl-service) and collection fails.
_ATTEST_SUBJECT = "eas:uid:0xatteststub"
_ATTEST_PAYLOAD = b'{"uid":"0xatteststub","schema":"public.v0"}'
_RELAY_SUBJECT = "https://relay.test.example/health"
_RELAY_PAYLOAD = b"ok"


def _digest(payload: bytes) -> str:
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def test_sanitize_subject_attestation_ok():
    assert sanitize_subject("public_attestation", _ATTEST_SUBJECT) == _ATTEST_SUBJECT


def test_sanitize_subject_rejects_private_relay():
    with pytest.raises(AttestSubjectError):
        sanitize_subject("public_relay", "https://10.0.0.8/health")
    with pytest.raises(AttestSubjectError):
        sanitize_subject("public_relay", "https://relay.ts.net/health")
    with pytest.raises(AttestSubjectError):
        sanitize_subject("public_relay", "http://relay.test.example/health")
    with pytest.raises(AttestSubjectError):
        sanitize_subject("public_relay", "https://user:secret@relay.test.example/health")


def test_sanitize_subject_rejects_empty_and_spaces():
    with pytest.raises(AttestSubjectError):
        sanitize_subject("public_attestation", "")
    with pytest.raises(AttestSubjectError):
        sanitize_subject("public_attestation", "eas uid")


def test_load_settings_rejects_unknown_mode(monkeypatch):
    monkeypatch.setenv("ORACLES_UPSTREAM", "chain-rpc")
    with pytest.raises(OraclesConfigError):
        load_oracles_settings()


@pytest.mark.asyncio
async def test_http_upstream_digests_and_drops_body():
    async def fetch(url: str) -> FetchResult:
        assert url == _RELAY_SUBJECT
        return FetchResult(status_code=200, body=_RELAY_PAYLOAD)

    upstream = HttpAttestUpstream(fetch=fetch)
    seen = await upstream.observe(kind="public_relay", subject=_RELAY_SUBJECT)
    assert seen.status == "observed"
    assert seen.digest == sha256_digest(_RELAY_PAYLOAD)
    assert seen.upstream == "http"
    assert _RELAY_PAYLOAD.decode() not in (seen.digest or "")


@pytest.mark.asyncio
async def test_http_upstream_unreachable_on_fetch_error():
    async def fetch(_url: str) -> FetchResult:
        raise TimeoutError("no live rpc")

    upstream = HttpAttestUpstream(fetch=fetch)
    seen = await upstream.observe(kind="public_relay", subject=_RELAY_SUBJECT)
    assert seen.status == "unreachable"
    assert seen.digest is None


@pytest.mark.asyncio
async def test_http_upstream_attestation_uses_mock_fallback():
    async def fetch(_url: str) -> FetchResult:
        raise AssertionError("attestation must not hit HTTP fetch")

    mock = MockAttestUpstream(registry={("public_attestation", _ATTEST_SUBJECT): _ATTEST_PAYLOAD})
    upstream = HttpAttestUpstream(fetch=fetch, fallback=mock)
    seen = await upstream.observe(kind="public_attestation", subject=_ATTEST_SUBJECT)
    assert seen.status == "observed"
    assert seen.digest == _digest(_ATTEST_PAYLOAD)
    assert seen.upstream == "mock"


@pytest.mark.asyncio
async def test_health(http_client):
    r = await http_client.get("/api/v1/health/")
    assert r.status_code == 200, r.text
    assert r.json()["status"] == "Ok"


@pytest.mark.asyncio
async def test_attest_public_attestation_happy_path(http_client, tenant_headers, event_sink):
    r = await http_client.post(
        "/api/v1/oracles/v0/attest",
        headers=tenant_headers,
        json={"kind": "public_attestation", "subject": _ATTEST_SUBJECT, "clientHint": "s3rch-next"},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["ok"] is True
    assert body["kind"] == "public_attestation"
    assert body["subject"] == _ATTEST_SUBJECT
    assert body["status"] == "observed"
    assert body["digest"] == _digest(_ATTEST_PAYLOAD)
    assert body["upstream"] == "mock"
    assert "observedAt" in body
    assert _ATTEST_PAYLOAD.decode() not in r.text
    assert event_sink == []


@pytest.mark.asyncio
async def test_attest_public_relay_happy_path(http_client, tenant_headers):
    r = await http_client.post(
        "/api/v1/oracles/v0/attest",
        headers=tenant_headers,
        json={"kind": "public_relay", "subject": _RELAY_SUBJECT},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["ok"] is True
    assert body["status"] == "observed"
    assert body["digest"] == _digest(_RELAY_PAYLOAD)
    assert "ok" != body["digest"]


@pytest.mark.asyncio
async def test_attest_default_mock_upstream_without_injection(event_sink, monkeypatch, tenant_headers):
    from api.core import config as api_config
    from oracles_service.app import create_app

    monkeypatch.setattr(
        api_config.settings,
        "database_url",
        "postgresql+asyncpg://x:x@localhost:1/x",
    )
    monkeypatch.setattr(api_config.settings, "kafka_bootstrap_servers", None)
    monkeypatch.setattr(api_config.settings, "service_name", "oracles-service-test")
    app = create_app(test_event_sink=event_sink, enable_db_middleware=False)

    import httpx
    from asgi_lifespan import LifespanManager

    async with LifespanManager(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            r = await client.post(
                "/api/v1/oracles/v0/attest",
                headers=tenant_headers,
                json={"kind": "public_attestation", "subject": _ATTEST_SUBJECT},
            )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["ok"] is False
    assert body["status"] == "not_found"
    assert body["upstream"] == "mock"
    assert event_sink == []


@pytest.mark.asyncio
async def test_attest_bearer_api_key(http_client, tenant_a):
    r = await http_client.post(
        "/api/v1/oracles/v0/attest",
        headers={
            "X-Tenant-ID": str(tenant_a),
            "Authorization": "Bearer pk_test.oracles-service",
        },
        json={"kind": "public_attestation", "subject": _ATTEST_SUBJECT},
    )
    assert r.status_code == 200, r.text
    assert r.json()["ok"] is True


@pytest.mark.asyncio
async def test_http_upstream_status_mapping():
    async def not_found(_url: str) -> FetchResult:
        return FetchResult(status_code=404, body=b"gone")

    async def server_error(_url: str) -> FetchResult:
        return FetchResult(status_code=502, body=b"bad gateway")

    async def other(_url: str) -> FetchResult:
        return FetchResult(status_code=403, body=b"no")

    unseen = await HttpAttestUpstream(fetch=not_found).observe(
        kind="public_relay", subject=_RELAY_SUBJECT
    )
    assert unseen.status == "not_found"
    err = await HttpAttestUpstream(fetch=server_error).observe(
        kind="public_relay", subject=_RELAY_SUBJECT
    )
    assert err.status == "error"
    blocked = await HttpAttestUpstream(fetch=other).observe(
        kind="public_relay", subject=_RELAY_SUBJECT
    )
    assert blocked.status == "unreachable"


@pytest.mark.asyncio
async def test_attest_unknown_subject_not_found(http_client, tenant_headers):
    r = await http_client.post(
        "/api/v1/oracles/v0/attest",
        headers=tenant_headers,
        json={"kind": "public_attestation", "subject": "eas:uid:0xmissing"},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["ok"] is False
    assert body["status"] == "not_found"
    assert body["digest"] is None


@pytest.mark.asyncio
async def test_attest_unauth_401(http_client, tenant_a):
    r = await http_client.post(
        "/api/v1/oracles/v0/attest",
        headers={"X-Tenant-ID": str(tenant_a)},
        json={"kind": "public_attestation", "subject": _ATTEST_SUBJECT},
    )
    assert r.status_code == 401
    assert r.json()["detail"] == ATTEST_AUTH_REQUIRED


@pytest.mark.asyncio
async def test_attest_missing_tenant_400(http_client):
    r = await http_client.post(
        "/api/v1/oracles/v0/attest",
        headers={"X-Api-Key": "pk_test.oracles-service"},
        json={"kind": "public_attestation", "subject": _ATTEST_SUBJECT},
    )
    assert r.status_code == 400


@pytest.mark.asyncio
async def test_attest_rejects_private_relay_400(http_client, tenant_headers):
    r = await http_client.post(
        "/api/v1/oracles/v0/attest",
        headers=tenant_headers,
        json={"kind": "public_relay", "subject": "https://127.0.0.1/health"},
    )
    assert r.status_code == 400


@pytest.mark.asyncio
async def test_attest_service_exchange_jwt(http_client, tenant_a):
    from api.infrastructure.security.api_key_exchange_jwt import mint_api_key_session_jwt

    token = mint_api_key_session_jwt(
        key_record_id=tenant_a,
        tenant_id=tenant_a,
        scopes=["oracles:attest"],
        purpose="service",
    )
    r = await http_client.post(
        "/api/v1/oracles/v0/attest",
        headers={
            "X-Tenant-ID": str(tenant_a),
            "Authorization": f"Bearer {token}",
        },
        json={"kind": "public_attestation", "subject": _ATTEST_SUBJECT},
    )
    assert r.status_code == 200, r.text
    assert r.json()["ok"] is True


@pytest.mark.asyncio
async def test_attest_rejects_ir_and_renter_purpose(http_client, tenant_a):
    from api.infrastructure.security.api_key_exchange_jwt import mint_api_key_session_jwt

    for purpose in ("ir", "renter"):
        token = mint_api_key_session_jwt(
            key_record_id=tenant_a,
            tenant_id=tenant_a,
            scopes=["oracles:attest"],
            purpose=purpose,
        )
        r = await http_client.post(
            "/api/v1/oracles/v0/attest",
            headers={
                "X-Tenant-ID": str(tenant_a),
                "Authorization": f"Bearer {token}",
            },
            json={"kind": "public_attestation", "subject": _ATTEST_SUBJECT},
        )
        assert r.status_code == 401, purpose
        assert r.json()["detail"] == ATTEST_PURPOSE_REQUIRED


@pytest.mark.asyncio
async def test_attest_rejects_hypermesh_identities(http_client, tenant_a):
    for token in ("hm_rtr_not-a-key", "hm_dev_not-a-key", "hm_site_not-a-key", "hm1.not-a-ticket"):
        r = await http_client.post(
            "/api/v1/oracles/v0/attest",
            headers={
                "X-Tenant-ID": str(tenant_a),
                "Authorization": f"Bearer {token}",
            },
            json={"kind": "public_attestation", "subject": _ATTEST_SUBJECT},
        )
        assert r.status_code == 401, token


@pytest.mark.asyncio
async def test_attest_bad_upstream_mode_fail_closed(http_client, tenant_headers, monkeypatch):
    monkeypatch.setenv("ORACLES_UPSTREAM", "rpc")
    r = await http_client.post(
        "/api/v1/oracles/v0/attest",
        headers=tenant_headers,
        json={"kind": "public_attestation", "subject": _ATTEST_SUBJECT},
    )
    assert r.status_code == 503
    assert "ORACLES_UPSTREAM" in r.json()["detail"]


@pytest.mark.asyncio
async def test_openapi_includes_attest(http_client):
    r = await http_client.get("/openapi.json")
    assert r.status_code == 200
    spec = r.json()
    assert "/api/v1/health/" in spec["paths"]
    assert "/api/v1/oracles/v0/attest" in spec["paths"]
    schemas = spec["components"]["schemas"]
    assert "AttestRequest" in schemas
    assert "kind" in schemas["AttestRequest"]["properties"]
    assert "subject" in schemas["AttestRequest"]["properties"]
    assert "clientHint" in schemas["AttestRequest"]["properties"]
    assert "AttestResponse" in schemas
    assert "observedAt" in schemas["AttestResponse"]["properties"]
    assert "digest" in schemas["AttestResponse"]["properties"]
    schemes = spec["components"]["securitySchemes"]
    assert "ApiKeyAuth" in schemes
    assert schemes["ApiKeyAuth"]["name"] == "X-Api-Key"
