# Oracles attest v0

Integrator contract for s3r.ch (and later peers). In-repo only. Do not copy this onto s3r.ch pages.

Locks: FyberLabs/hypermesh-docs `open-services.md` (2026-09-02). This service is the **oracles/validators product shape** after TURN allocate. Crypto payments are the next slice, not this one. Wallet door parked. ACA env wire stays held.

Folder id **`oracles`** (OpenAPI id `oracles`, package `oracles_service`). Not `validators`: the product is the open hop others can offer; a validator is one upstream, not the noun.

## Endpoint

```
POST /api/v1/oracles/v0/attest
```

Compose host **8013**. Gateway edge prefix `/api/v1/oracles`. Merged OpenAPI id `oracles` (`/_upstream/oracles/…`).

Health reuses the existing unauthenticated pattern: `GET /api/v1/health/`.

### Auth

Reuse Panopticon product patterns (marketplace tenant + API key / purpose grant), same family as TURN allocate — **machine/service**, not a Hypermesh lease.

| Header | Required | Notes |
| --- | --- | --- |
| `X-Tenant-ID` | yes | Marketplace tenant UUID |
| `X-Api-Key` | one of | `prefix.secret` product API key. Hold this **server-side** in the Next app (or a thin product client). Never Gun. Never `localStorage`. Never `NEXT_PUBLIC_*`. |
| `Authorization: Bearer` | one of | Same API key, **or** a gateway-minted API-key exchange JWT with `purpose=service` |

Rejects: missing key (401), Hypermesh `hm_rtr_` / `hm_dev_` / `hm_site_` / `hm1.` identities, exchange JWT with `purpose=renter` or `purpose=ir`.

**s3r.ch SIWE hop (later, not this slice):** s3r.ch login stays SIWE on the s3r.ch origin. That app verifies the session itself, then the **Next server** calls attest with the product API key. Do not invent SIWE-as-Panopticon-login. Do not use Keycloak as s3r.ch login. Wallet door (SIWE↔Keycloak) stays parked.

Browser-first stays in the client: SIWE ecrecover, ERC-1271, ENS reverse+forward. Panopticon only observes public subjects we cannot honestly do client-side.

Production gateway already validates `X-Api-Key` via `api-keys-service` and can mint the exchange JWT. This service also gates so it can run standalone for tests.

### Request

```json
{
  "kind": "public_attestation",
  "subject": "eas:uid:0xatteststub",
  "clientHint": "s3rch-next"
}
```

| Field | Type | Notes |
| --- | --- | --- |
| `kind` | `"public_attestation"` \| `"public_relay"` | One verb, two public subjects. Product may lock a second verb later (`/verify`). |
| `subject` | string, 1–256 | Attestation identifier (`[A-Za-z0-9:._/-]`) or a **public https** URL. No credentials in the URL. `public_relay` must be https on a public hostname (rejects Tailscale / RFC1918 / loopback). |
| `clientHint` | string, optional | Integrator label. Sanitized by schema length only in v0. Not persisted. Not written to Gun. |

### Response

```json
{
  "ok": true,
  "kind": "public_attestation",
  "subject": "eas:uid:0xatteststub",
  "status": "observed",
  "observedAt": "2026-09-09T03:36:00+00:00",
  "digest": "sha256:9f86d081884c7d659a2feaa0c55ad015a3bf4f1b2b0b822cd15d6c15b0f00a08",
  "upstream": "mock"
}
```

| Field | Notes |
| --- | --- |
| `ok` | `true` only when `status` is `observed` |
| `status` | `observed` \| `not_found` \| `unreachable` \| `error` |
| `observedAt` | UTC timestamp of this hop |
| `digest` | `sha256:` + hex of **upstream bytes**. Null when nothing was observed. The bytes themselves are never returned. |
| `upstream` | `"mock"` (default) or `"http"` (injected fetch for `public_relay`) |

v0 publishes **no** domain events. No prompt bodies, API keys, or observed payloads on the bus or Gun.

### Fail-soft (same spirit as TURN → STUN + `/gun`)

When the subject cannot be observed, attest still returns **HTTP 200** with `ok: false` and `status` in `{not_found, unreachable, error}`. That is **fail-soft for the consumer** — not a hard 5xx that forces the client to abort.

```json
{
  "ok": false,
  "kind": "public_attestation",
  "subject": "eas:uid:0xmissing",
  "status": "not_found",
  "observedAt": "2026-09-09T03:36:00+00:00",
  "digest": null,
  "upstream": "mock"
}
```

Consumer (s3r.ch Next later) should treat that like TURN fail-soft (unsigned / failed allocate → keep STUN + `/gun`):

- Keep browser-first SIWE ecrecover, ERC-1271, ENS reverse+forward.
- Do not invent a grant from a missing digest. Do not persist `null` as proof.
- Optional UI honesty that the oracle hop did not observe. Do not copy this contract onto s3r.ch pages.

Auth and config failures still **hard-fail**. Those are not soft:

| HTTP | When |
| --- | --- |
| 400 | Missing/invalid `X-Tenant-ID`, or `subject` fails public-https / identifier rules |
| 401 | Missing product API key, Hypermesh `hm_*` identity, or JWT `purpose` other than `service` |
| 503 | `ORACLES_UPSTREAM` missing/unknown (or other fail-closed config) |

Do not change live s3r.ch in this PR.

### How s3r.ch Next would hop later

```ts
// Next server only. Product API key stays server-side.
const { ok, status, digest, observedAt } = await attest({
  kind: "public_attestation",
  subject: uid,
  clientHint: "s3rch-next",
})
// HTTP 200 + ok === false (not_found | unreachable | error): fail-soft.
// Keep browser-first SIWE / ENS / ERC-1271. Do not invent a grant from a missing digest.
// Do not persist digest as a grant. Do not put the API key on Gun.
```

## Config

| Env | Role |
| --- | --- |
| `ORACLES_UPSTREAM` | `mock` (default) or `http`. Unknown values **fail closed** (503). |
| `ORACLES_HTTP_TIMEOUT_S` | Fetch timeout when `http`. Default `3`. |

`http` mode GETs a public https `public_relay` subject via an **injected** fetch. `public_attestation` still uses the in-memory mock map — v0 does not open a chain RPC. Tests inject a fake fetch / registry. Compose stays on `mock`.

## Non-goals (this product / this PR)

- No live chain RPC, archive node, or five-chain farm
- No SIWE ecrecover, ERC-1271, or ENS reverse+forward (browser-first)
- No crypto payments, Stripe, Hypermesh Checkout/lease, or marketplace crypto-bar
- No wallet door / SIWE↔Keycloak
- No Gun seed / snapshot, chat, rooms, or grant minting
- No SIWE-as-Panopticon-login; no Keycloak as s3r.ch login
- No Hypermesh WG / Tailscale as browser relay
- No tokenomics, paid metering, or s3r.ch UI consume
- No growing the s3r.ch Azure App Service into this
- No domain events in v0 (if later: `controlplane.events.v1` only)
- ACA env wire stays held

## Graduation

A later `POST /api/v1/oracles/v0/verify` may take client-supplied evidence and return valid/invalid against the same oracle view. Cutover is this base URL, not a second client protocol. Metering / paid access can come later; the API stays public/open so others can sell the same shape.

Sequence: TURN allocate → oracles (this) → crypto payments. Wallet door parked.
