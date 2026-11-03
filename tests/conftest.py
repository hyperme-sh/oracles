from __future__ import annotations

import uuid

import pytest

from api.core import config as api_config
from api.infrastructure.security import keycloak_jwt as kc_jwt

from oracles_service.upstream import MockAttestUpstream

# Keep in sync with tests/test_oracles_service.py. Do not `from tests.conftest import …` —
# after `uv sync --all-packages` that name resolves to another workspace
# member's tests/ (CI: core/acl-service) and collection fails.
TEST_ATTEST_SUBJECT = "eas:uid:0xatteststub"
TEST_ATTEST_PAYLOAD = b'{"uid":"0xatteststub","schema":"public.v0"}'
TEST_RELAY_SUBJECT = "https://relay.test.example/health"
TEST_RELAY_PAYLOAD = b"ok"


@pytest.fixture(autouse=True)
def _clear_keycloak_validator_cache() -> None:
    kc_jwt._validator_singleton.cache_clear()
    yield
    kc_jwt._validator_singleton.cache_clear()


@pytest.fixture(autouse=True)
def _oracles_env(monkeypatch):
    monkeypatch.setenv("ORACLES_UPSTREAM", "mock")
    monkeypatch.setenv("ORACLES_HTTP_TIMEOUT_S", "3")
    monkeypatch.setattr(
        api_config.settings,
        "api_key_exchange_jwt_secret",
        "test-api-key-exchange-secret-min-32-chars!!",
    )


@pytest.fixture
def event_sink() -> list:
    return []


@pytest.fixture
def attest_upstream() -> MockAttestUpstream:
    return MockAttestUpstream(
        registry={
            ("public_attestation", TEST_ATTEST_SUBJECT): TEST_ATTEST_PAYLOAD,
            ("public_relay", TEST_RELAY_SUBJECT): TEST_RELAY_PAYLOAD,
        }
    )


@pytest.fixture
def app(event_sink, attest_upstream, monkeypatch):
    monkeypatch.setattr(
        api_config.settings,
        "database_url",
        "postgresql+asyncpg://x:x@localhost:1/x",
    )
    monkeypatch.setattr(api_config.settings, "service_name", "oracles-service-test")

    from oracles_service.app import create_app

    return create_app(
        test_event_sink=event_sink,
        enable_db_middleware=False,
        attest_upstream=attest_upstream,
    )


@pytest.fixture
async def http_client(app):
    import httpx
    from asgi_lifespan import LifespanManager

    async with LifespanManager(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            yield client


@pytest.fixture
def tenant_a() -> uuid.UUID:
    return uuid.UUID("aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee")


@pytest.fixture
def tenant_headers(tenant_a: uuid.UUID) -> dict[str, str]:
    return {
        "X-Tenant-ID": str(tenant_a),
        "X-Api-Key": "pk_test.oracles-service",
    }
