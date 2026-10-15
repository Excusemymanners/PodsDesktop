#!/usr/bin/env bash
# Builds a self-contained dist/PodsDesktop binary with PyInstaller (run inside the project venv:
#   .venv/bin/pip install -e ".[gui]" pyinstaller && ./packaging/build-linux.sh ).
# The binary runs on distributions with a glibc at least as new as the build machine's.
set -euo pipefail
cd "$(dirname "$0")/.."
python=".venv/bin/python"; [ -x "$python" ] || python="python3"
"$python" -m PyInstaller --noconfirm --clean --onefile --windowed --name PodsDesktop \
    --collect-data podsdesktop \
    --collect-all bleak --collect-submodules dbus_fast \
    --hidden-import podsdesktop.core.bluetooth_linux --hidden-import podsdesktop.gui.app \
    podsdesktop/__main__.py
echo "built: dist/PodsDesktop"
