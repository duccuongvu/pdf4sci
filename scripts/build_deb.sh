#!/bin/bash
# Build the .deb package from the PyInstaller bundle. Run build_bundle.sh
# first. Building needs no root/sudo -- `dpkg-deb --root-owner-group`
# stamps root ownership in the archive's metadata without requiring the
# builder to actually be root. (Installing it with `apt install ./*.deb`
# still needs sudo, as normal for any .deb.)
set -euo pipefail
cd "$(dirname "$0")/.."

VERSION=0.1.0
BUNDLE=packaging/pyinstaller/dist/pdf4sci-gui
if [ ! -d "$BUNDLE" ]; then
    echo "Bundle not found at $BUNDLE -- run scripts/build_bundle.sh first." >&2
    exit 1
fi

cd packaging/deb
PKGROOT="pdf4sci_${VERSION}_amd64"
rm -rf "$PKGROOT"
mkdir -p "$PKGROOT/DEBIAN" "$PKGROOT/opt/pdf4sci" "$PKGROOT/usr/bin" "$PKGROOT/usr/share/applications"

for size in 16 32 48 64 128 256 512; do
    mkdir -p "$PKGROOT/usr/share/icons/hicolor/${size}x${size}/apps"
    cp "../../pdf4sci/assets/icons/${size}.png" \
        "$PKGROOT/usr/share/icons/hicolor/${size}x${size}/apps/pdf4sci.png"
done

cp -r "../pyinstaller/dist/pdf4sci-gui/." "$PKGROOT/opt/pdf4sci/"
chmod +x "$PKGROOT/opt/pdf4sci/pdf4sci-gui"
ln -sf /opt/pdf4sci/pdf4sci-gui "$PKGROOT/usr/bin/pdf4sci-gui"

cat > "$PKGROOT/usr/share/applications/pdf4sci.desktop" <<'EOF'
[Desktop Entry]
Name=pdf4sci
Comment=Compress scientific PDF files
Exec=pdf4sci-gui %f
Icon=pdf4sci
Terminal=false
Type=Application
Categories=Office;Utility;
MimeType=application/pdf;
EOF

INSTALLED_SIZE=$(du -sk "$PKGROOT/opt" "$PKGROOT/usr" | awk '{sum+=$1} END {print sum}')
cat > "$PKGROOT/DEBIAN/control" <<EOF
Package: pdf4sci
Version: ${VERSION}
Section: utils
Priority: optional
Architecture: amd64
Maintainer: Duc Cuong Vu <vdcuong2002@gmail.com>
Installed-Size: ${INSTALLED_SIZE}
Description: Scientific PDF Optimizer
 pdf4sci compresses PDFs to a target file size while preserving text,
 fonts, equations, and vector graphics -- only oversized raster images
 are re-encoded, and only when it actually helps. This package installs
 the native desktop GUI as a self-contained bundle (no system Python or
 Qt installation required).
EOF

cat > "$PKGROOT/DEBIAN/postinst" <<'EOF'
#!/bin/sh
set -e
if command -v update-desktop-database >/dev/null 2>&1; then
    update-desktop-database -q /usr/share/applications || true
fi
if command -v gtk-update-icon-cache >/dev/null 2>&1; then
    gtk-update-icon-cache -q /usr/share/icons/hicolor || true
fi
exit 0
EOF
chmod 755 "$PKGROOT/DEBIAN/postinst"

mkdir -p dist
dpkg-deb --build --root-owner-group "$PKGROOT" "dist/pdf4sci_${VERSION}_amd64.deb"

echo "Package: packaging/deb/dist/pdf4sci_${VERSION}_amd64.deb"
ls -la "dist/pdf4sci_${VERSION}_amd64.deb"
