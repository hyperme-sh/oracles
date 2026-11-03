"""Mockable attest protocol. Tests inject a fake; CI never hits live chain RPC.

Default is an in-memory mock registry. HTTP mode GETs a public https
subject for ``public_relay`` via an injected fetch callable. Observed
bytes stay inside the protocol — callers only see a sha256 digest.
"""

from __future__ import annotations

import asyncio
import hashlib
import ipaddress
import math
import socket
from dataclasses import dataclass, field
from typing import Awaitable, Callable, Literal, Protocol

from oracles_service.settings import OraclesSettings

AttestKind = Literal["public_attestation", "public_relay"]
ObserveStatus = Literal["observed", "not_found", "unreachable", "error"]


@dataclass(frozen=True)
class FetchResult:
    """Minimal HTTP result. body is hashed then discarded by the protocol."""

    status_code: int
    body: bytes


FetchFn = Callable[[str], Awaitable[FetchResult]]


@dataclass(frozen=True)
class UpstreamObservation:
    status: ObserveStatus
    digest: str | None
    upstream: str


def sha256_digest(payload: bytes) -> str:
    return "sha256:" + hashlib.sha256(payload).hexdigest()


class AttestUpstream(Protocol):
    async def observe(self, *, kind: AttestKind, subject: str) -> UpstreamObservation: ...


@dataclass
class MockAttestUpstream:
    """In-memory public subjects. No RPC. Seed in tests or leave empty."""

    registry: dict[tuple[str, str], bytes] = field(default_factory=dict)
    name: str = "mock"

    async def observe(self, *, kind: AttestKind, subject: str) -> UpstreamObservation:
        payload = self.registry.get((kind, subject))
        if payload is None:
            status: ObserveStatus = "not_found" if kind == "public_attestation" else "unreachable"
            return UpstreamObservation(status=status, digest=None, upstream=self.name)
        return UpstreamObservation(
            status="observed",
            digest=sha256_digest(payload),
            upstream=self.name,
        )


@dataclass
class HttpAttestUpstream:
    """public_relay via injected fetch. public_attestation stays on the mock map.

    Does not open a chain RPC. Pass ``fetch`` from tests; production may
    wire httpx. Never return ``body`` to the API layer.
    """

    fetch: FetchFn
    fallback: MockAttestUpstream = field(default_factory=MockAttestUpstream)
    name: str = "http"

    async def observe(self, *, kind: AttestKind, subject: str) -> UpstreamObservation:
        if kind != "public_relay":
            return await self.fallback.observe(kind=kind, subject=subject)
        try:
            result = await self.fetch(subject)
        except Exception:
            return UpstreamObservation(status="unreachable", digest=None, upstream=self.name)
        if result.status_code == 404:
            return UpstreamObservation(status="not_found", digest=None, upstream=self.name)
        if result.status_code >= 500 or result.status_code < 0:
            return UpstreamObservation(status="error", digest=None, upstream=self.name)
        if result.status_code != 200:
            return UpstreamObservation(status="unreachable", digest=None, upstream=self.name)
        return UpstreamObservation(
            status="observed",
            digest=sha256_digest(result.body),
            upstream=self.name,
        )


def default_upstream(settings: OraclesSettings, *, fetch: FetchFn | None = None) -> AttestUpstream:
    mock = MockAttestUpstream()
    if settings.upstream == "http":
        if fetch is None:
            fetch = _default_http_fetch(settings.http_timeout_s)
        return HttpAttestUpstream(fetch=fetch, fallback=mock)
    return mock


MAX_RELAY_BYTES = 1024 * 1024


async def _public_address(host: str, port: int) -> str:
    """Resolve once and reject the entire answer set if any address is non-public."""
    answers = await asyncio.get_running_loop().getaddrinfo(
        host, port, type=socket.SOCK_STREAM
    )
    if not answers:
        raise ValueError("relay has no addresses")
    addresses = []
    for _, _, _, _, sockaddr in answers:
        address = ipaddress.ip_address(sockaddr[0])
        effective = getattr(address, "ipv4_mapped", None) or address
        if not effective.is_global or effective.is_multicast or "%" in str(address):
            raise ValueError("relay resolved to a non-public address")
        addresses.append(str(address))
    return addresses[0]


def _default_http_fetch(timeout_s: float) -> FetchFn:
    async def _fetch(url: str) -> FetchResult:
        import httpx
        from oracles_service.settings import sanitize_subject

        if not math.isfinite(timeout_s) or timeout_s <= 0:
            raise ValueError("relay timeout must be finite and positive")

        # The deadline includes DNS, connection setup and the entire response.
        async with asyncio.timeout(timeout_s):
            target = httpx.URL(sanitize_subject("public_relay", url))
            address = await _public_address(target.host, target.port or 443)
            # Connect only to the validated numeric address. Keep the original
            # authority for HTTP routing and TLS certificate/SNI verification.
            pinned = target.copy_with(host=address)
            async with httpx.AsyncClient(
                timeout=timeout_s, follow_redirects=False, trust_env=False
            ) as client:
                async with client.stream(
                    "GET", pinned,
                    headers={"Host": target.netloc.decode("ascii"), "Accept-Encoding": "identity"},
                    extensions={"sni_hostname": target.host},
                ) as response:
                    if response.status_code != 200:
                        return FetchResult(status_code=response.status_code, body=b"")
                    # Reject compression so decompression cannot bypass the cap.
                    if response.headers.get("content-encoding", "identity").lower() != "identity":
                        raise ValueError("encoded relay response is not supported")
                    body = bytearray()
                    async for chunk in response.aiter_raw():
                        if len(body) + len(chunk) > MAX_RELAY_BYTES:
                            raise ValueError("relay response exceeds byte limit")
                        body.extend(chunk)
                    return FetchResult(status_code=response.status_code, body=bytes(body))

    return _fetch
