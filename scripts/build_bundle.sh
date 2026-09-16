#!/bin/bash
# Build a standalone PyInstaller bundle of the native GUI.
#
# Run from the dev conda env (needs pdf4sci[gui] + pyinstaller installed):
#   pip install -e ".[gui]" pyinstaller
#   ./scripts/build_bundle.sh
#
# Output: packaging/pyinstaller/dist/pdf4sci-gui/  (onedir bundle)
set -euo pipefail
cd "$(dirname "$0")/.."

rm -rf packaging/pyinstaller/dist packaging/pyinstaller/build packaging/pyinstaller/pdf4sci-gui.spec

pyinstaller --name pdf4sci-gui --onedir --windowed \
    --add-data "$(pwd)/pdf4sci/assets/icons:pdf4sci/assets/icons" \
    --paths . \
    --exclude-module matplotlib --exclude-module scipy --exclude-module pandas \
    --exclude-module tkinter --exclude-module PyQt5 --exclude-module PyQt6 \
    --distpath packaging/pyinstaller/dist \
    --workpath packaging/pyinstaller/build \
    --specpath packaging/pyinstaller \
    packaging/pyinstaller/run_gui.py

echo "Bundle: packaging/pyinstaller/dist/pdf4sci-gui/"
du -sh packaging/pyinstaller/dist/pdf4sci-gui/
