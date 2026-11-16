> Superseded: runtime images no longer download or include source archives.
> LICENSE/NOTICE and dependency legal texts remain. The records below describe
> prior builds and are retained for historical review, not current build steps.

# LGPL/MPL source and replacement preparation

The prepared image carries upstream source archives at
`/usr/share/doc/oracles-service/sources`, with URLs, versions and SHA-256 values
in `index.json`. These files travel inside the container; there is no separate
Actions archive or package publication. The build refuses changed downloads,
changed installed package versions, changed native files or a changed native
SBOM. Source hashes identify the bytes supplied; TEST still uses moving channels.

## Included materials

- certifi 2026.10.23, jwcrypto 1.6.1, orjson 3.13.0 and psycopg 3.3.7: complete
  upstream source releases, including their build configuration and license texts.
  orjson's release includes vendored Rust dependencies and C sources.
- psycopg-binary 3.3.7: the exact upstream release commit archive, including
  `tools/ci/copy_to_binary.py`, native build recipes and the PostgreSQL patch.
  The manifest pairs the qualified CPython 3.13 Linux x86_64 wheel's extension
  and shared-library bytes with the matching source records.
- PostgreSQL 18.6, OpenSSL 3.5.8 and OpenLDAP 2.6.14 source archives named by the
  upstream binary build recipe; CentOS source RPMs matching the wheel's declared
  cyrus-sasl, keyutils, krb5, e2fsprogs, libselinux and pcre package versions.
- Full GPL-3.0 text, alongside the LGPL texts already present for jwcrypto,
  psycopg and psycopg-binary. Existing upstream notices remain unchanged.

The archives are upstream source, not executables to run during extraction.
Source RPMs include the package spec and distribution patches. Use the upstream
build scripts with the versions recorded in the source index when rebuilding.
This records source provenance; it does not assert a bit-for-bit native rebuild.

## Extracting materials from a distributed image

Once an image is published, a recipient can copy its sources without starting
its service:

```sh
container=$(docker create "$IMAGE")
docker cp "$container:/usr/share/doc/oracles-service" ./oracles-service-docs
docker rm "$container"
```

`$IMAGE` is the container the recipient obtained. These extraction steps do not
change registry visibility. The existing main workflow publishes the moving TEST
channel after its source and replacement checks pass.

## Replacing libraries

No runtime signature check restricts recipient modifications. Package/hash
checks belong to preparation CI, not application startup. For a compatible
replacement wheel built by the recipient, a derived image can use:

```dockerfile
ARG IMAGE
FROM ${IMAGE}
USER root
COPY replacement-wheels/ /tmp/replacement-wheels/
RUN /usr/local/bin/python -m pip --python /opt/runtime/bin/python install \
    --no-deps --force-reinstall /tmp/replacement-wheels/*.whl \
    && rm -rf /tmp/replacement-wheels
USER 65532:65532
```

Keep the original wheel filenames in `replacement-wheels/`. A native
replacement must retain the expected ABI and library names, or rebuild the
extension and its dependencies together using the supplied upstream recipes.
The existing Apache license adds no restriction on debugging modifications to
these libraries. Their own license terms continue to apply.

The CI replacement contract bind-mounts a real jwcrypto package with a synthetic
added marker and a real libpq library with an unused trailing marker. It imports
the modified package and loads the ABI-compatible library with network disabled.
It starts no service or database. This demonstrates replacement is not blocked;
it is not a rebuilt-library functional or deployment qualification.

## Native source mapping

All 15 bundled native libraries now map to source versions. The upstream
psycopg build log identifies the exact manylinux image used for this wheel.
Its immutable config records libxcrypt 4.5.2 and the source archive hash.
The bundle includes that source, the original build scripts and a small original
binary layer for provenance comparison only. Container verification checks the
OCI metadata, source recipe and matching code/read-only-data sections against
the installed wheel. It does not execute the original binary layer.

The 18 archives include source packages, build scripts and that comparison layer.
`publication_cleared: false` remains deliberate: history treatment and publication
authority are separate from source preparation. No full bit-identical native
rebuild is claimed.

This slice addresses the five recorded LGPL/MPL Python distributions. It does
not claim a complete rebuild of every base-image or transitive native component.
Repository-history treatment and public publication remain separate #993 work.
The relevant upstream terms are [MPL-2.0](https://www.mozilla.org/en-US/MPL/2.0/)
and [LGPL-3.0](https://www.gnu.org/licenses/lgpl-3.0.html); copied texts in the image
remain authoritative for each component.

## Public source test vectors in the image scan

The pristine upstream archives contain public cryptographic test vectors,
example private keys, checksums and API declarations. The image scan still
examines them. Known findings are classified only when the archive hash, member
hash, scanner rule and line match the reviewed CI baseline. Runtime files,
changed archives/members and new finding coordinates are never exempted. Reports
print coordinates and counts, not the matched contents. These upstream vectors
are never used as deployment credentials.
