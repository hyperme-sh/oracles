# Oracles

Public attestation and relay observations. Package oracles-service 0.1.0;
factory oracles_service.app.create_app; entry point python -m oracles_service.main.

POST /api/v1/oracles/v0/attest uses the marketplace tenant and a product API key
or purpose=service exchange token. GET /api/v1/health/ is unauthenticated.
edge-routes.json retains the edge routing contract. Default upstream is mock;
the service has no persistent state and publishes no domain events in this version.

## Development

Use Python 3.13 and uv 0.11.26 with read access to the seven pinned private
repositories named in .github/workflows/package.yml.

    uv sync --frozen
    bash scripts/check-package.sh

The existing suite runs from source, a normal fresh installed wheel outside the
checkout and an sdist-rebuilt wheel. Both wheel payloads must match runtime bytes.
HTTP tests use mock upstreams and disable database middleware; they require no
live chain or relay access. Service/container wiring and consumer acceptance
require separate validation before deployment.

The main-only hosted workflow uses pinned actions, read-only contents and exact
repository credential headers. Actions remains disabled pending approved scoped
DEPENDENCY_READ_TOKEN access and hosted-worker policy. No publishing or deployment.

HTTP relay fetching rejects non-public DNS answers and pins the connection to a
validated address while preserving TLS hostname verification. It bypasses environment
proxies, does not follow redirects, and accepts only identity-encoded responses up
to 1 MiB. The configured timeout bounds the whole fetch, including DNS and streaming;
failures return an unreachable observation without a digest.
