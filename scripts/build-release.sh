#!/usr/bin/env bash
# Cross-compile session-zx for every platform tmux runs on, then checksum.
# Output: dist/session-zx_<version>_<os>_<arch>[.tar.gz] and dist/checksums.txt
#
#   VERSION=v1.2.3 scripts/build-release.sh
set -euo pipefail

VERSION="${VERSION:-dev}"
OUT=dist
rm -rf "$OUT"
mkdir -p "$OUT"

# No cgo: the binary must run on any glibc/musl box without extra libraries.
export CGO_ENABLED=0

for target in linux/amd64 linux/arm64 darwin/amd64 darwin/arm64; do
  os="${target%%/*}"
  arch="${target##*/}"
  name="session-zx_${VERSION}_${os}_${arch}"

  echo "building $name"
  GOOS="$os" GOARCH="$arch" go build -trimpath \
    -ldflags "-s -w" -o "$OUT/session-zx" .

  tar -czf "$OUT/${name}.tar.gz" -C "$OUT" session-zx
  rm "$OUT/session-zx"
done

( cd "$OUT" && sha256sum ./*.tar.gz > checksums.txt )

echo "=== dist ==="
ls -l "$OUT"
