#!/bin/bash
# Build everything and collect release artifacts + checksums into
# dist/release/. Requires the dev conda env with pdf4sci[gui] and
# pyinstaller installed.
set -euo pipefail
cd "$(dirname "$0")/.."

./scripts/build_bundle.sh
./scripts/build_appimage.sh
./scripts/build_deb.sh

mkdir -p dist/release
cp packaging/appimage/dist/pdf4sci-x86_64.AppImage dist/release/
cp packaging/deb/dist/pdf4sci_0.1.0_amd64.deb dist/release/

(cd dist/release && sha256sum pdf4sci-x86_64.AppImage pdf4sci_0.1.0_amd64.deb > SHA256SUMS)

echo
echo "Release artifacts in dist/release/:"
ls -la dist/release/
echo
cat dist/release/SHA256SUMS
