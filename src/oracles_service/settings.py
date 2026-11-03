"""Upstream mode and public-subject rules.

v0 is mock-first so CI never needs live chain RPC. HTTP mode is an
injected fetch for public_relay only — still no archive node, no
SIWE/ENS/ERC-1271 (those stay in the browser).
"""

from __future__ import annotations

import ipaddress
import os
from dataclasses import dataclass
from typing import Literal
from urllib.parse import urlparse

UPSTREAM_ENV = "ORACLES_UPSTREAM"
HTTP_TIMEOUT_ENV = "ORACLES_HTTP_TIMEOUT_S"
DEFAULT_UPSTREAM = "mock"
DEFAULT_HTTP_TIMEOUT_S = 3.0
SUBJECT_MAX_LEN = 256

_PRIVATE_RELAY = "public_relay subject must be a public https URL"
_BAD_SUBJECT = "subject is invalid"


class OraclesConfigError(Exception):
    """Misconfiguration. Attest maps this to 503 fail-closed."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


class AttestSubjectError(ValueError):
    """Caller-supplied subject failed validation (400)."""

    def __init__(self, reason: str) -> None:
        super().__init__(reason)
        self.reason = reason


@dataclass(frozen=True)
class OraclesSettings:
    upstream: Literal["mock", "http"]
    http_timeout_s: float


def _looks_private_or_tailscale(host: str) -> bool:
    """Reject Tailscale / PE-only / loopback so this is not a privileged intranet oracle."""

    lowered = host.strip().lower().rstrip(".")
    if not lowered:
        return True
    if lowered in {"localhost", "localhost.localdomain"}:
        return True
    if lowered.endswith(".ts.net") or lowered.endswith(".tailscale.net"):
        return True
    if "%" in lowered:
        lowered = lowered.split("%", 1)[0]
    try:
        ip = ipaddress.ip_address(lowered)
    except ValueError:
        return False
    cgnat = ipaddress.ip_network("100.64.0.0/10")
    return bool(
        ip.is_private
        or ip.is_loopback
        or ip.is_link_local
        or ip.is_multicast
        or ip.is_unspecified
        or ip.is_reserved
        or ip in cgnat
    )


def require_public_host(host: str | None) -> str:
    cleaned = (host or "").strip()
    if not cleaned or _looks_private_or_tailscale(cleaned):
        raise AttestSubjectError(_PRIVATE_RELAY)
    return cleaned


def sanitize_subject(kind: str, subject: str) -> str:
    """Public identifier or https URL. Never credentials, never RFC1918 relay."""

    raw = (subject or "").strip()
    if not raw:
        raise AttestSubjectError("subject is required")
    if len(raw) > SUBJECT_MAX_LEN:
        raise AttestSubjectError("subject too long")
    if any(ch.isspace() for ch in raw):
        raise AttestSubjectError(_BAD_SUBJECT)
    if "://" in raw:
        parsed = urlparse(raw)
        if parsed.username or parsed.password:
            raise AttestSubjectError("subject must not include credentials")
        if parsed.scheme != "https":
            raise AttestSubjectError("URL subject must be https")
        require_public_host(parsed.hostname)
        if kind == "public_relay" and not parsed.netloc:
            raise AttestSubjectError(_PRIVATE_RELAY)
        return raw
    if kind == "public_relay":
        raise AttestSubjectError(_PRIVATE_RELAY)
    allowed = set("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789:._/-")
    if any(ch not in allowed for ch in raw):
        raise AttestSubjectError(_BAD_SUBJECT)
    return raw


def load_oracles_settings() -> OraclesSettings:
    raw = (os.environ.get(UPSTREAM_ENV) or DEFAULT_UPSTREAM).strip().lower()
    if raw not in {"mock", "http"}:
        raise OraclesConfigError("ORACLES_UPSTREAM must be mock or http")
    timeout_raw = (os.environ.get(HTTP_TIMEOUT_ENV) or "").strip()
    timeout = DEFAULT_HTTP_TIMEOUT_S if not timeout_raw else float(timeout_raw)
    if timeout <= 0:
        raise OraclesConfigError("ORACLES_HTTP_TIMEOUT_S must be > 0")
    return OraclesSettings(upstream=raw, http_timeout_s=timeout)  # type: ignore[arg-type]
