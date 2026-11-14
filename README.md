# Oracles

Oracles provides scoped attestation and relay observations. The service version
remains `0.1.0`, under the existing Apache-2.0 license.

`POST /api/v1/oracles/v0/attest` accepts a tenant and a product API key or a
`purpose=service` exchange token. `GET /api/v1/health/` is unauthenticated.
The default upstream is a mock. This version has no persistent state and publishes
no domain events. `edge-routes.json` defines the edge route contract.

## Development checks

Use Python 3.13 and uv 0.11.26:

```sh
bash scripts/check-package.sh --fixtures
```

The unit and mocked HTTP contracts run against source, a fresh installed wheel,
and a wheel rebuilt from the source archive. Wheels are temporary build inputs,
not service distributions. Fixtures are verified against the exact locked public
Git revisions. No shared service or live chain is contacted. Full integration/e2e
belongs to Infra's scheduled `oracles-installed` lane and is never started by hand.

## Runtime and preparation

The Dockerfile installs the qualified wheel and its locked dependencies into an
unprivileged runtime. It does not retain the package archive inside the image.
The existing main workflow validates and publishes its TEST channel independently
of other services. Production publication remains separately authorized.

Read-only preparation CI builds without dependency credentials, scans committed
source and every final-image layer, checks for private content and hosted payment
modules, and verifies copied installed licenses/notices. A non-shallow history scan
reports historical hosted content and rejects unexpected secret findings. It verifies that installed
Oracles runtime bytes match the committed source. Temporary scan outputs are
removed; no package or scan artifact is uploaded.

All seven locked Git dependency owners are public. The image build verifies that
the exact revisions can be fetched anonymously. The existing dependency-token
configuration is retired only after this anonymous path passes CI.

See [preparation status](docs/public-preparation.md). Repository/image visibility
and remaining third-party notice follow-ups remain with [Infra #993](https://github.com/FyberLabs/infra/issues/993).

## Relay safety contract

HTTP relay fetching rejects non-public DNS answers and pins the connection to a
validated address while preserving TLS hostname verification. It bypasses environment
proxies, does not follow redirects, and accepts only identity-encoded responses up
to 1 MiB. The timeout bounds DNS and streaming together. Failures return an
unreachable observation without a digest. Tenant/purpose authorization, subject
validation and attestation expiry remain mandatory.
