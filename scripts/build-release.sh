#!/usr/bin/env bash
# Cross-compile hoppy for every platform tmux runs on, then checksum.
# Output: dist/hoppy_<version>_<os>_<arch>[.tar.gz] and dist/checksums.txt
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
  name="hoppy_${VERSION}_${os}_${arch}"

  echo "building $name"
  GOOS="$os" GOARCH="$arch" go build -trimpath \
    -ldflags "-s -w" -o "$OUT/hoppy" .

  tar -czf "$OUT/${name}.tar.gz" -C "$OUT" hoppy
  rm "$OUT/hoppy"
done

( cd "$OUT" && sha256sum ./*.tar.gz > checksums.txt )

echo "=== dist ==="
ls -l "$OUT"
