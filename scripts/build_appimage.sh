#!/bin/bash
# Build the AppImage from the PyInstaller bundle. Run build_bundle.sh first.
#
# Downloads appimagetool on first run (cached under packaging/appimage/).
# If the system has no libfuse2, appimagetool itself can't run as an
# AppImage -- this script extracts it once and runs the extracted AppRun
# instead, which needs no FUSE at all (only *running* the final .AppImage
# needs FUSE; building one does not).
set -euo pipefail
cd "$(dirname "$0")/.."

BUNDLE=packaging/pyinstaller/dist/pdf4sci-gui
if [ ! -d "$BUNDLE" ]; then
    echo "Bundle not found at $BUNDLE -- run scripts/build_bundle.sh first." >&2
    exit 1
fi

cd packaging/appimage

if [ ! -x appimagetool-x86_64.AppImage ]; then
    curl -sL -o appimagetool-x86_64.AppImage \
        https://github.com/AppImage/AppImageKit/releases/download/continuous/appimagetool-x86_64.AppImage
    chmod +x appimagetool-x86_64.AppImage
fi

if [ ! -x squashfs-root/AppRun ]; then
    ./appimagetool-x86_64.AppImage --appimage-extract >/dev/null 2>&1 || true
fi
APPIMAGETOOL=./squashfs-root/AppRun
if [ ! -x "$APPIMAGETOOL" ]; then
    APPIMAGETOOL=./appimagetool-x86_64.AppImage  # system has libfuse2; run directly
fi

rm -rf AppDir
mkdir -p AppDir/usr/bin AppDir/usr/share/applications AppDir/usr/share/icons/hicolor/256x256/apps
cp -r ../pyinstaller/dist/pdf4sci-gui AppDir/usr/bin/pdf4sci-gui
cp ../../pdf4sci/assets/icons/256.png AppDir/usr/share/icons/hicolor/256x256/apps/pdf4sci.png
cp AppDir/usr/share/icons/hicolor/256x256/apps/pdf4sci.png AppDir/pdf4sci.png
cp AppDir/pdf4sci.desktop AppDir/usr/share/applications/pdf4sci.desktop 2>/dev/null || true

cat > AppDir/pdf4sci.desktop <<'EOF'
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
cp AppDir/pdf4sci.desktop AppDir/usr/share/applications/pdf4sci.desktop

cat > AppDir/AppRun <<'EOF'
#!/bin/sh
HERE="$(dirname "$(readlink -f "$0")")"
exec "$HERE/usr/bin/pdf4sci-gui/pdf4sci-gui" "$@"
EOF
chmod +x AppDir/AppRun

mkdir -p dist
ARCH=x86_64 "$APPIMAGETOOL" AppDir dist/pdf4sci-x86_64.AppImage

echo "AppImage: packaging/appimage/dist/pdf4sci-x86_64.AppImage"
ls -la dist/pdf4sci-x86_64.AppImage
