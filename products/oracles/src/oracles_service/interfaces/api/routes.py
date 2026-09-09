"""POST /api/v1/oracles/v0/attest — public attestation / relay check."""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, HTTPException, Request, status

from oracles_service.auth import require_service_grant
from oracles_service.domain.models import AttestRequest, AttestResponse
from oracles_service.settings import (
    AttestSubjectError,
    OraclesConfigError,
    load_oracles_settings,
    sanitize_subject,
)
from oracles_service.tenant import require_tenant_id
from oracles_service.upstream import AttestUpstream, default_upstream

router = APIRouter(prefix="/oracles", tags=["oracles"])

_ATTEST_SECURITY = [{"ApiKeyAuth": []}, {"BearerAuth": []}]


def _upstream(request: Request) -> AttestUpstream:
    existing = getattr(request.app.state, "attest_upstream", None)
    if existing is not None:
        return existing
    try:
        cfg = load_oracles_settings()
    except OraclesConfigError as exc:
        raise HTTPException(status_code=503, detail=exc.reason) from exc
    built = default_upstream(cfg)
    request.app.state.attest_upstream = built
    return built


@router.post(
    "/v0/attest",
    response_model=AttestResponse,
    response_model_by_alias=True,
    status_code=status.HTTP_200_OK,
    openapi_extra={"security": _ATTEST_SECURITY},
    summary="Observe a public attestation or relay subject",
    description=(
        "Returns a structured observation (status + sha256 digest) from a "
        "mockable upstream. Product API key or purpose=service exchange JWT. "
        "Does not run SIWE / ERC-1271 / ENS (browser-first). Does not write "
        "Gun. Observed bytes and secrets are never returned."
    ),
)
async def attest_public(request: Request, body: AttestRequest) -> AttestResponse:
    require_tenant_id(request)
    require_service_grant(request)
    try:
        subject = sanitize_subject(body.kind, body.subject)
    except AttestSubjectError as exc:
        raise HTTPException(status_code=400, detail=exc.reason) from exc

    try:
        load_oracles_settings()
    except OraclesConfigError as exc:
        raise HTTPException(status_code=503, detail=exc.reason) from exc

    observation = await _upstream(request).observe(kind=body.kind, subject=subject)
    return AttestResponse(
        ok=observation.status == "observed",
        kind=body.kind,
        subject=subject,
        status=observation.status,
        observed_at=datetime.now(UTC),
        digest=observation.digest,
        upstream=observation.upstream,
    )
