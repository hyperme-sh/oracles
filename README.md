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

The main-only shared-runner workflow uses pinned actions, read-only contents and exact
repository credential headers. Actions remains disabled pending approved scoped
DEPENDENCY_READ_TOKEN access and shared-runner qualification. No publishing or deployment.

HTTP relay fetching rejects non-public DNS answers and pins the connection to a
validated address while preserving TLS hostname verification. It bypasses environment
proxies, does not follow redirects, and accepts only identity-encoded responses up
to 1 MiB. The configured timeout bounds the whole fetch, including DNS and streaming;
failures return an unreachable observation without a digest.

## Release channels

Main validation retains its exact qualified files in Actions artifacts. It does
not create GitHub releases or tags. Historical `test-<commit>` prereleases remain
qualification evidence and do not establish an accepted stable release.

Stable publication requires an explicit `vMAJOR.MINOR.PATCH` tag, the exact
successful main validation artifact, compatible declared contracts and an actual
immutable stable baseline. The publisher independently verifies that evidence;
successful caller jobs alone cannot establish acceptance. Missing evidence and
first-stable bootstrap remain closed. Package qualification, coordinated consumer
acceptance and runtime deployment remain separate.

### Package preparation

`bash scripts/check-package.sh --fixtures` runs the existing source, fresh-wheel
and rebuilt-source-archive consumers without private Git credentials. Fixtures
are verified existing 0.24 dependency artifacts; the manifest records their exact
source revisions, digests and original Actions provenance. The verifier checks
root metadata, the complete active lock graph and transitive wheel metadata.
Explicit private extras and unrecognized conditional pins fail closed.

The read-only pull-request workflow retains tested wheels, source archives and
artifact-derived runtime and installer contracts as Actions artifacts. It does
not publish releases. The private dependency graph is prepared on 0.24 using immutable Git pins and
matching artifacts. The owner version remains 0.1.0; coordinated owner-version
adoption and stable release acceptance remain unfinished.

`releases/qualification` records a verified prior immutable test snapshot and its
original Actions provenance. It is qualification evidence, not an accepted stable
release, and must not configure the stable release baseline variable.
`releases/prepared` identifies the exact prepared wheel by digest. Package tests
verify that binding and compare the rebuilt source archive's contract. Contracts
include runtime resources, Python constraints, dependencies, extras and entry
points. An explicit qualification-only transition lists the old and new private
pins and binds them to the complete 0.24 fixture graph. Runtime bytes, Python
constraints, registry requirements, extras and entry points must remain unchanged.
Source, installed-wheel and rebuilt-archive consumers qualify this exact graph;
this does not waive stable admission or authorize arbitrary dependency changes.
Existing owner test boundaries and live/provider qualification requirements apply.

## Test qualification and stable acceptance

GitHub `test-<commit>` prereleases are development snapshots. Their embedded
package version does not reserve a stable version. Artifact and consumer evidence
belongs under `releases/qualification`. Owning-package and artifact validation
remain separate from stable release admission. Future test receipts must carry
an explicit non-stable classification.

`releases/accepted` and `SPANOPTICON_RELEASE_BASELINE_SHA` are reserved for an
actual immutable stable GitHub release. The pinned shared guard verifies the live
release channel, stable tag source and asset digests; a test snapshot cannot
become accepted through a provenance label. No stable baseline is recorded until
that release exists. Stable publication remains closed without a valid baseline;
first stable bootstrap and coordinated release qualification remain separate.
No stable version, approval prerequisite or deployment is introduced here.

### Actions qualification and stable publication

Main merges and workflow completion do not publish GitHub test releases. Exact
qualification files remain in Actions artifacts with finite retention. The pinned
publisher independently verifies a real immutable stable baseline and refuses
qualification snapshots, even if a caller job reports success. Existing valid
stable records are retained; no release, version change, deployment or human
approval prerequisite is introduced by this correction.
