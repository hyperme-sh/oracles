# Historical distribution review

This is a read-only review. It neither deletes nor rewrites Git objects, registry
versions, tags or releases, and it does not change repository/package visibility.
No running TEST channel is pinned or moved by the review.

## Source findings

[Source classification records](../../.github/workflows/historical-source-findings.json) classifies the 162 matches in 12
historical wheel blobs reported by the earlier reachable-history review. Each
entry identifies the Git object, member and SHA-256; no source contents or
credential values are copied into the report. The non-shallow history check
compares these classifications with actual archived bytes and reports new,
unclassified matches separately.

The matches include 75 database migrations, 36 domain contracts, 15 persistence
implementation files, 12 event contracts, 6 business implementation files,
6 configuration/metric references, 3 provider adapters, 3 messaging integrations,
3 dependency wiring files and 3 dependency metadata files. Counts include repeated
members across different historical wheel versions. Contracts or references are
not silently treated as private implementation, nor do classifications establish
permission to distribute the historical implementations. All remain retained;
content disposition is separate from this review and constrained by the owner's
no-rewrite instruction.

## Older GHCR images

The hosted `Historical image review` workflow uses a read-only package token to
paginate every currently retained tag in `hyperme-sh/oracles/runtime`. It records
tag-to-manifest observations, deduplicates immutable Linux amd64 digests and
reports other platform descriptors without claiming they were scanned. Each
matrix job pulls by the observed digest, removes its registry credentials and
inspects every saved layer, including files deleted by subsequent layers. It
never starts an image or imports its Python packages.

CI logs contain `REGISTRY_REVIEW_INVENTORY`, `HISTORICAL_IMAGE_REVIEW` and per-digest
secret-scan outcomes. Hosted code, private paths and deployment-value matches are
reported by path/hash; observed package versions and legal-file locations are
reported by layer. These observations are not a reconstructed final filesystem
or a legal clearance. Secret matches print coordinates, never matched contents.
The old Pydeck 0.9.3 notebook source map has two scanner matches that are public
loaders.gl class/function identifiers. The exact PyPI wheel and member hashes
are recorded with the rule and line; only unchanged source-map bytes at the
recorded location are classified as public. Other source vectors and public
metadata retain the existing narrow checks. Unexpected findings fail the scan; ordinary historical
content findings remain reports rather than new approval gates.

The jobs upload no Actions archives, publish no review image and do not modify
TEST. Package publication continues through the existing moving GHCR TEST workflow.
Integration/e2e remains exclusively in nightly CI.

## Coverage limits

Tag enumeration is a point-in-time observation, not an atomic registry snapshot.
A moved tag does not change the already recorded digest being reviewed. Untagged
or deleted versions, non-amd64 platforms, hidden/deleted Git refs, remote LFS
content and other registries are outside this inventory. Local package-version
API access was denied for lack of read:packages; hosted CI uses repository-scoped
read access rather than expanding that credential.

The ACR inventory is separate from this GHCR enumeration. Read-only access must
use Infra's configured Azure subscription, not a workstation's unrelated default.
The one-off `Archived registry image review` workflow accepts an observed digest
and reads a temporary pull-only credential through repository secrets. Its
operator supplies the registry host and `oracles` repository scope, verifies the
credential's pull-only claims, runs the static job and deletes those temporary
secrets afterward. It does not create Azure identities or role grants, write
registry tags, start a container, or invoke nightly integration/e2e.

ACR inventory and reviewed digest results are recorded in Infra #993. Untagged
and deleted versions cannot be inferred from GHCR tags; they require their own
registry inventory. The report must identify exactly which registry snapshot
was compared with the completed digest scans.

### Retained ACR image observed 2026-11-14

The configured Infra subscription contains one retained `oracles` manifest,
`sha256:e196877bf41709a0f9d757c275806bc1d986d623c233fff51836e7be0b79090e`,
tagged `verification-test-f5e1e8d08d3cb013a46fddc8b08f50eeaf557cf2`.
Hosted static review [43608261141](https://github.com/hyperme-sh/oracles/actions/runs/43608261141)
inspected all six saved layers without starting the image. It reported 1,702
hosted-code matches, 187 installed distribution metadata records, and no files
under the standardized `/usr/share/doc/oracles-service` legal bundle path.
The user configuration was `65532:65532`. These are layer observations, not
permission to distribute the image or a claim that every dependency lacks legal
texts. The hosted implementation remains retained and uncleared for public
redistribution; no image or tag was changed.

The two secret-scanner findings point to the Pydeck 0.9.3 source map
at its older `app/.venv` installation path. The public-file classifier accepts
that path only with the same exact upstream member hash, rule and line used for
the current installation path. A changed member still fails classification.
Download raw job logs when reviewing large JSON reports: the CLI's formatted
run-log output omitted the large report and subsequent lines in this run.
