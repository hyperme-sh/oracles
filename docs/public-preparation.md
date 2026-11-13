# Oracles preparation status

Oracles #30 prepares source and the service image. It does not publish a repository
or change the existing Apache-2.0 license. LICENSE is retained in source and in the
installed distribution. A root NOTICE file is absent; any required owner notice
text must be settled under Infra #993 before public redistribution. Installed
third-party license declarations and notice paths are reported by CI, including
missing metadata that needs review. Base-image copyright files remain installed.

The locked source owners are controlplane-api, controlplane-core, controlplane-db,
controlplane-events, controlplane-identity, controlplane-tenancy and user-service's
operator-ban-store contract. These repositories are public; exact revisions stay
in uv.lock and the verified unit-test fixture manifest. An anonymous image build
must succeed before any dependency credential is retired.

The source scanner preserves AGENTS.md and checks the current committed tree.
Every final-image layer is scanned, including lower-layer files removed later.
Private paths, hosted payment modules and embedded private deployment addresses
fail preparation. Only reviewed public metadata may have narrow scanner exceptions.
Notebook browser extensions are omitted from this API runtime; installed package
licenses remain intact.

Successful preparation does not establish public visibility, publication authority,
shared TEST readiness or production readiness. Historical Git and older published
images have a separate pre-public review under Infra #993. No Git history is rewritten.
