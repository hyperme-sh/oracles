#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
scratch=$(mktemp -d)
trap 'rm -rf -- "$scratch"' EXIT
python3 scripts/review_history.py "$scratch/blobs" "$scratch/history.json"
version=8.30.1
archive="gitleaks_${version}_linux_x64.tar.gz"
curl --fail --silent --show-error --location "https://github.com/gitleaks/gitleaks/releases/download/v${version}/${archive}" -o "$scratch/$archive"
printf '%s  %s\n' 551f6fc83ea457d62a0d98237cbad105af8d557003051f41f3e7ca7b3f2470eb "$scratch/$archive" | sha256sum --check
mkdir "$scratch/tool"
tar -xzf "$scratch/$archive" -C "$scratch/tool" gitleaks
status=0
"$scratch/tool/gitleaks" dir "$scratch/blobs" --config .gitleaks-history.toml --redact --no-banner --ignore-gitleaks-allow \
  --report-format json --report-path "$scratch/findings.json" || status=$?
# Never print historical source or secret contents, only object/member coordinates.
python3 - "$scratch/history.json" "$scratch/findings.json" <<'PY'
import json, sys
from pathlib import Path
print(Path(sys.argv[1]).read_text())
p = Path(sys.argv[2])
if p.exists():
    for row in json.loads(p.read_text()):
        print(json.dumps({key: row.get(key) for key in ('File', 'StartLine', 'RuleID')}))
PY
exit "$status"
