#!/usr/bin/env bash
# CI-only import contracts: no service, database or external network is started.
set -euo pipefail
image=${1:?Prepared image required}
scratch=$(mktemp -d)
container=
cleanup() { if [[ -n "$container" ]]; then docker rm "$container" >/dev/null; fi; rm -rf -- "$scratch"; }
trap cleanup EXIT
container=$(docker create "$image")
site=/opt/runtime/lib/python3.13/site-packages
docker cp "$container:$site/jwcrypto" "$scratch/jwcrypto"
docker cp "$container:$site/psycopg_binary.libs" "$scratch/psycopg_binary.libs"
# A synthetic added marker demonstrates that the loader accepts recipient edits.
printf '\nreplacement_contract_marker = True\n' >> "$scratch/jwcrypto/__init__.py"
# An unused trailing marker preserves the library ABI while changing its bytes.
python3 - "$scratch" <<'PY'
from pathlib import Path
import sys
library, = (Path(sys.argv[1]) / 'psycopg_binary.libs').glob('libpq-*.so.*')
with library.open('ab') as stream:
    stream.write(b'\0recipient-replacement-contract\0')
PY
chmod -R a+rX "$scratch"
docker run --rm --network none --read-only --cap-drop ALL --security-opt no-new-privileges \
  --mount "type=bind,src=$scratch/jwcrypto,dst=$site/jwcrypto,readonly" \
  --mount "type=bind,src=$scratch/psycopg_binary.libs,dst=$site/psycopg_binary.libs,readonly" \
  --entrypoint /opt/runtime/bin/python "$image" -I -c \
  'import jwcrypto, psycopg; assert jwcrypto.replacement_contract_marker; assert psycopg.pq.__impl__ == "binary"; assert psycopg.pq.version() >= 180000; print("Modified Python package and ABI-compatible native library loaded")'
