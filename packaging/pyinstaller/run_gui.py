"""PyInstaller entry point: bundling needs a plain script (not `python -m
pdf4sci.gui.app`), so this just imports and calls the real entry point."""

from pdf4sci.gui.app import main

if __name__ == "__main__":
    raise SystemExit(main())
