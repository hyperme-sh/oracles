#!/usr/bin/env bash
# Static image review only. Never starts a container or modifies a registry tag.
set -euo pipefail
cd "$(dirname "$0")/.."
digest=${1:?Digest required}
[[ "$digest" =~ ^sha256:[0-9a-f]{64}$ ]]
image="ghcr.io/hyperme-sh/oracles/runtime@$digest"
scratch=$(mktemp -d)
export DOCKER_CONFIG="$scratch/docker"
cleanup() { docker image rm "$image" >/dev/null 2>&1 || true; rm -rf -- "$scratch"; }
trap cleanup EXIT
trap 'exit 130' INT
trap 'exit 143' TERM
mkdir -p "$DOCKER_CONFIG" "$scratch/tool" "$scratch/layers"
printf '%s' "$REGISTRY_TOKEN" | docker login ghcr.io --username "$REGISTRY_USER" --password-stdin
unset REGISTRY_TOKEN
docker pull --platform linux/amd64 "$image"
rm -rf "$DOCKER_CONFIG"
docker save --output "$scratch/image.tar" "$image"
uv python install 3.13
python=$(uv python find 3.13)
"$python" scripts/review_image.py "$scratch/image.tar" "$scratch/layers" "$digest"
version=8.30.1
archive="gitleaks_${version}_linux_x64.tar.gz"
curl --fail --silent --show-error --location "https://github.com/gitleaks/gitleaks/releases/download/v${version}/${archive}" -o "$scratch/$archive"
printf '%s  %s\n' 551f6fc83ea457d62a0d98237cbad105af8d557003051f41f3e7ca7b3f2470eb "$scratch/$archive" | sha256sum --check
tar -xzf "$scratch/$archive" -C "$scratch/tool" gitleaks
status=0
"$scratch/tool/gitleaks" dir "$scratch/layers" --config .gitleaks.toml --redact --no-banner \
  --max-archive-depth 3 --ignore-gitleaks-allow --report-format json --report-path "$scratch/findings.json" || status=$?
if [[ "$status" == 1 && -s "$scratch/findings.json" ]]; then
  "$python" scripts/classify_historical_findings.py "$scratch/findings.json" "$scratch/layers"
elif [[ "$status" != 0 ]]; then
  exit "$status"
fi
printf 'HISTORICAL_IMAGE_SECRET_SCAN_PASSED=%s\n' "$digest"
