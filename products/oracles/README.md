# Oracles (public attestation / relay check)

Second Panopticon **open product** on the client-mesh services plane (after TURN allocate). Copied from [`products/template/`](../template/), same family as [`products/turn/`](../turn/). A thin hop for oracles/validators we cannot honestly do in the browser. This is **not** Hypermesh rental, not a Gun seed, not s3r.ch App Service.

Product folder id **`oracles`** (OpenAPI id `oracles`, package `oracles_service`). Chosen over `validators`: open-services frames the service category as “oracles we cannot do in-browser”; a validator is one kind of upstream, not the product noun.

Locks (do not amend): FyberLabs/hypermesh-docs `open-services.md` (2026-09-02). Integrator shape: [`docs/oracles-attest-v0.md`](docs/oracles-attest-v0.md). Plane spine §C (s3r.ch catalog): [`docs/multi-plane-spine-v0.md`](../../docs/multi-plane-spine-v0.md).

## What this service is

Compose host port **8013**. In-memory / no persist. Default upstream is **mock** (no live chain RPC). v0 publishes **no** domain events. If a later slice publishes, only `controlplane.events.v1`.

| Piece | Path |
|-------|------|
| Attest | `POST /api/v1/oracles/v0/attest` (HTTP 200 + `ok: false` is fail-soft; 401/503 stay hard) |
| Health | `GET /api/v1/health/` |

Auth: marketplace `X-Tenant-ID` + product API key (`X-Api-Key` or Bearer) or a purpose=`service` API-key exchange JWT. Same family as TURN allocate. Not Hypermesh lease, not `hm_rtr_` / renter / ir.

Browser-first stays in the client: SIWE ecrecover, ERC-1271, ENS reverse+forward. This door is a public attestation / relay observation only.

## Run locally

From the repo root (after `uv lock` if you just added this package):

```bash
docker compose up -d --build postgres kafka oracles-service
```

- Health: http://localhost:8013/api/v1/health/
- OpenAPI / Swagger: http://localhost:8013/docs
- Gateway merge: `CPEDGE_ORACLES_SERVICE_URL` (compose sets it). Merged paths are prefixed `/_upstream/oracles/…`.
- Gateway prefix: `/api/v1/oracles*` → :8013.

Without Docker:

```bash
cd products/oracles
uv run pytest -q
uv run python -m oracles_service.main
```

## Tests

Hermetic. No live chain RPC.

```bash
cd products/oracles && uv run pytest --cov=oracles_service --cov-report=term-missing -q
```

HTTP tests disable DB middleware (same idea as the template) so they run without Docker.
