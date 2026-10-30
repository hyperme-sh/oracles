"""X-Tenant-ID parsing (marketplace tenant). Works with or without GUC middleware."""

from __future__ import annotations

import uuid

from fastapi import HTTPException, Request


def require_tenant_id(request: Request) -> uuid.UUID:
    raw = request.headers.get("X-Tenant-ID")
    if not raw:
        raise HTTPException(status_code=400, detail="X-Tenant-ID header is required")
    try:
        tid = uuid.UUID(str(raw))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid X-Tenant-ID") from exc
    state_tid = getattr(request.state, "tenant_id", None)
    if state_tid is not None and state_tid != tid:
        raise HTTPException(
            status_code=403,
            detail="X-Tenant-ID must match session tenant",
        )
    return tid
