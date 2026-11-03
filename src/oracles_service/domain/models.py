"""Attest request/response. JSON names match the integrator contract exactly."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

AttestKind = Literal["public_attestation", "public_relay"]
AttestStatus = Literal["observed", "not_found", "unreachable", "error"]


class AttestRequest(BaseModel):
    """POST /api/v1/oracles/v0/attest body."""

    model_config = ConfigDict(populate_by_name=True)

    kind: AttestKind
    subject: str = Field(..., min_length=1, max_length=256)
    client_hint: str | None = Field(
        default=None,
        max_length=128,
        validation_alias="clientHint",
        serialization_alias="clientHint",
    )


class AttestResponse(BaseModel):
    """Structured observation. digest is sha256 of upstream bytes — never the bytes."""

    model_config = ConfigDict(populate_by_name=True)

    ok: bool
    kind: AttestKind
    subject: str
    status: AttestStatus
    observed_at: datetime = Field(
        ...,
        validation_alias="observedAt",
        serialization_alias="observedAt",
    )
    digest: str | None = None
    upstream: str
