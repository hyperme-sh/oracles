"""Product API-key / purpose-grant gate for oracles attest.

Reuses the TURN / Hypermesh IR pattern: marketplace tenant +
machine/service API key (X-Api-Key or Bearer) or an API-key
exchange JWT with purpose=service. Format-only on the raw key.

Does not invent SIWE-as-Panopticon-login. Does not accept Keycloak
as s3r.ch login. Hypermesh renter/ir purposes and hm_* identities
stay out.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Literal

from fastapi import HTTPException, Request

from oracles_service.tenant import require_tenant_id

ATTEST_AUTH_REQUIRED = "product API key required"
ATTEST_PURPOSE_REQUIRED = "purpose service API key required"
ATTEST_PURPOSE_SERVICE = "service"
TENANT_CLAIM = "https://panopticon.dev/tenant_id"

DEVICE_SECRET_HEAD = "hm_dev_"
ROUTER_SECRET_HEAD = "hm_rtr_"
SITE_TOKEN_HEAD = "hm_site_"
TICKET_PREFIX = "hm1."


class AttestUnauthorized(HTTPException):
    def __init__(self, detail: str = ATTEST_AUTH_REQUIRED) -> None:
        super().__init__(status_code=401, detail=detail)


@dataclass(frozen=True)
class ServiceGrant:
    kind: Literal["api_key", "exchange_jwt"]
    subject: str
    purpose: str


def looks_like_jwt(token: str) -> bool:
    if token.startswith((ROUTER_SECRET_HEAD, DEVICE_SECRET_HEAD, SITE_TOKEN_HEAD, TICKET_PREFIX)):
        return False
    parts = token.split(".")
    return len(parts) == 3 and all(parts)


def looks_like_api_key(token: str) -> bool:
    if token.startswith((ROUTER_SECRET_HEAD, DEVICE_SECRET_HEAD, SITE_TOKEN_HEAD, TICKET_PREFIX)):
        return False
    if looks_like_jwt(token):
        return False
    if "." not in token:
        return False
    prefix, secret = token.split(".", 1)
    return bool(prefix) and bool(secret)


def _bearer(request: Request) -> str | None:
    raw = request.headers.get("Authorization")
    if not raw:
        return None
    scheme, _, token = raw.partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        return None
    return token.strip()


def _api_key_header(request: Request) -> str | None:
    raw = request.headers.get("X-Api-Key") or request.headers.get("x-api-key")
    if not raw or not raw.strip():
        return None
    return raw.strip()


def _forbidden_identity(token: str) -> bool:
    return token.startswith((ROUTER_SECRET_HEAD, DEVICE_SECRET_HEAD, SITE_TOKEN_HEAD, TICKET_PREFIX))


def _subject_from_api_key(token: str) -> str:
    return token.split(".", 1)[0]


def _subject_from_jwt(claims: dict[str, Any]) -> str:
    raw = claims.get("sub")
    if raw:
        return str(raw)
    return "service"


def _tenant_matches(claims: dict[str, Any], tenant_id: str) -> bool:
    raw = claims.get(TENANT_CLAIM) or claims.get("tenant_id")
    if raw is None:
        return True
    return str(raw) == tenant_id


def _exchange_jwt_claims(token: str) -> dict[str, Any] | None:
    """Local decode of the gateway-minted API-key session JWT. Not Keycloak."""

    try:
        from api.infrastructure.security.api_key_exchange_jwt import (
            try_decode_api_key_session_jwt,
        )
    except Exception:
        return None
    return try_decode_api_key_session_jwt(token)


def require_service_grant(request: Request) -> ServiceGrant:
    """Machine/service product credential. Tenant header is required separately."""

    tenant_id = require_tenant_id(request)
    bearer = _bearer(request)
    header_key = _api_key_header(request)

    if bearer:
        if _forbidden_identity(bearer):
            raise AttestUnauthorized()
        if looks_like_jwt(bearer):
            claims = _exchange_jwt_claims(bearer)
            if claims is None or not _tenant_matches(claims, str(tenant_id)):
                raise AttestUnauthorized()
            purpose = str(claims.get("purpose") or "").strip().lower()
            if purpose != ATTEST_PURPOSE_SERVICE:
                raise AttestUnauthorized(ATTEST_PURPOSE_REQUIRED)
            return ServiceGrant(
                kind="exchange_jwt",
                subject=_subject_from_jwt(claims),
                purpose=ATTEST_PURPOSE_SERVICE,
            )
        if looks_like_api_key(bearer):
            return ServiceGrant(
                kind="api_key",
                subject=_subject_from_api_key(bearer),
                purpose=ATTEST_PURPOSE_SERVICE,
            )
        raise AttestUnauthorized()

    if header_key:
        if _forbidden_identity(header_key) or not looks_like_api_key(header_key):
            raise AttestUnauthorized()
        return ServiceGrant(
            kind="api_key",
            subject=_subject_from_api_key(header_key),
            purpose=ATTEST_PURPOSE_SERVICE,
        )

    raise AttestUnauthorized()
