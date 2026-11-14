# Oracles preparation status

Oracles #30 prepares source and the service image. It does not publish a repository
or change the existing Apache-2.0 license. LICENSE is retained in source and in the
installed distribution. The root NOTICE identifies the owner and preserves
third-party terms. Both texts are checked byte-for-byte in the wheel, rebuilt
source archive wheel and final image at `/usr/share/doc/oracles-service`. Installed
third-party license declarations and copied texts are recorded in the image at
`/usr/share/doc/oracles-service/third-party`. Builds reject missing texts,
incorrect supplement versions and changed hashes. The final-image check compares
the index against every installed distribution and verifies the copied bytes.
Base-image copyright files remain installed.

Streamlit 1.66.1 uses its exact upstream LICENSE and NOTICES. jwcrypto 1.6.1,
psycopg 3.3.7 and psycopg-binary 3.3.7 include the full GPL text referenced by
their LGPL terms; the binary package also retains the libxcrypt notices.
Verbatim upstream texts and source/version/hash records live under
`.github/workflows/third-party-notices`. These four locked wheel inventories
match the previously reviewed product-template inputs. operator-ban-store's
locked revision already includes its owner license and requires no supplement.
The [source and replacement preparation](../licenses/SOURCES.md) supplies 18
hash-bound archives and build records for the five declared LGPL/MPL packages.
All five locked source/wheel inventories match the reviewed product-template
inputs, including psycopg-binary 3.3.7. Final-image checks verify native bytes,
SBOM and libxcrypt build provenance. CI-only replacement checks load a modified
Python package and ABI-compatible native library without starting a service or
using network access. No full bit-identical native rebuild is claimed.

The locked source owners are controlplane-api, controlplane-core, controlplane-db,
controlplane-events, controlplane-identity, controlplane-tenancy and user-service's
operator-ban-store contract. These repositories are public; exact revisions stay
in uv.lock and the verified unit-test fixture manifest. Anonymous image CI passed for all locked revisions before the obsolete dependency
read token was removed. Registry publication retains its separate scoped credential.

The source scanner preserves AGENTS.md and checks the current committed tree.
Every final-image layer is scanned, including lower-layer files removed later.
Private paths, hosted payment modules and embedded private deployment addresses
fail preparation. Only reviewed public metadata may have narrow scanner exceptions.
Notebook browser extensions are omitted from this API runtime; installed package
licenses remain intact.

Successful preparation does not establish public visibility, publication authority,
shared TEST readiness or production readiness. The [reachable-history review](history-review.md)
records historical hosted-code findings; older published images remain outside
this current-image review. No Git history is rewritten.
