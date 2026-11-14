#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
uv python install 3.13
python=$(uv python find 3.13)
scratch=$(mktemp -d)
owned_image=1
image="oracles-preparation:$(git rev-parse HEAD)-$(basename "$scratch" | tr '[:upper:]' '[:lower:]')"
if [[ "$#" == 2 && "$1" == --image ]]; then image="$2"; owned_image=0
elif [[ "$#" != 0 ]]; then echo 'Usage: check-distribution.sh [--image IMAGE]' >&2; exit 2; fi
cleanup() { if [[ "$owned_image" == 1 ]]; then docker image rm "$image" >/dev/null 2>&1 || true; fi; rm -rf "$scratch"; }
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM
mkdir "$scratch/source" "$scratch/tool" "$scratch/layers"
git archive HEAD | tar -xf - -C "$scratch/source"
"$python" scripts/distribution_audit.py source "$scratch/source"
version=8.30.1
archive="gitleaks_${version}_linux_x64.tar.gz"
curl --fail --silent --show-error --location "https://github.com/gitleaks/gitleaks/releases/download/v${version}/${archive}" -o "$scratch/$archive"
printf '%s  %s\n' 551f6fc83ea457d62a0d98237cbad105af8d557003051f41f3e7ca7b3f2470eb "$scratch/$archive" | sha256sum --check
tar -xzf "$scratch/$archive" -C "$scratch/tool" gitleaks
scan() {
  local status=0
  "$scratch/tool/gitleaks" dir "$1" --config "$PWD/.gitleaks.toml" --redact --no-banner \
    --max-archive-depth 3 --ignore-gitleaks-allow --report-format json --report-path "$scratch/findings.json" || status=$?
  if [[ "$status" != 0 && -f "$scratch/findings.json" ]]; then
    "$python" - "$scratch/findings.json" <<'PYSCAN'
import json,sys
for row in json.load(open(sys.argv[1])):
    print(json.dumps({key:row.get(key) for key in ('File','StartLine','RuleID')}))
PYSCAN
  fi
  return "$status"
}
scan "$scratch/source"
# Build only the archived revision. Neither checkout credentials nor local files enter the context.
if [[ "$owned_image" == 1 ]]; then
  (cd "$scratch/source" && uv build --wheel --out-dir "$scratch/dist" &&
    uv export --frozen --no-dev --no-emit-project --no-hashes --format requirements-txt --output-file "$scratch/dist/requirements.txt")
  cp "$scratch/source/scripts/prepare_notices.py" "$scratch/dist/"
  cp -R "$scratch/source/.github/workflows/third-party-notices" "$scratch/dist/"
  docker build --label "org.opencontainers.image.revision=$(git rev-parse HEAD)" \
    --file "$scratch/source/Dockerfile" --tag "$image" "$scratch/dist"
fi
test "$(docker image inspect "$image" --format '{{ index .Config.Labels "org.opencontainers.image.revision" }}')" = "$(git rev-parse HEAD)"
docker save --output "$scratch/image.tar" "$image"
"$python" scripts/distribution_audit.py image "$scratch/image.tar" --output "$scratch/layers"
scan "$scratch/layers"
# Static metadata only: no server, database, credentials or external requests.
docker run --rm --network none --read-only --cap-drop ALL --security-opt no-new-privileges \
  --mount "type=bind,src=$PWD/scripts/distribution_audit.py,dst=/audit.py,readonly" \
  --mount "type=bind,src=$scratch/source,dst=/owner-source,readonly" \
  --mount "type=bind,src=$scratch/source/src,dst=/audit-source,readonly" \
  --entrypoint /opt/runtime/bin/python "$image" /audit.py installed /audit-source --owner-source /owner-source
printf 'Source and container checks passed for %s. Publication remains separately authorized.\n' "$(git rev-parse HEAD)"
