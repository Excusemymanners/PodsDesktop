#!/usr/bin/env bash
# Installs PodsDesktop for the current user: a venv in ~/.local/share/podsdesktop,
# a `podsdesktop` command in ~/.local/bin and a menu entry. No root needed.
set -euo pipefail
here="$(cd "$(dirname "$0")/.." && pwd)"
target="${XDG_DATA_HOME:-$HOME/.local/share}/podsdesktop"
bin="$HOME/.local/bin"
apps="${XDG_DATA_HOME:-$HOME/.local/share}/applications"

python3 -m venv "$target/venv"
"$target/venv/bin/pip" install --quiet --upgrade pip
"$target/venv/bin/pip" install --quiet "$here[gui]"
mkdir -p "$bin" "$apps"
ln -sf "$target/venv/bin/podsdesktop" "$bin/podsdesktop"
sed "s|^Exec=.*|Exec=$target/venv/bin/podsdesktop|" "$here/packaging/podsdesktop.desktop" > "$apps/podsdesktop.desktop"
echo "installed: $bin/podsdesktop (menu entry: PodsDesktop)"
echo "start it with: podsdesktop   |   battery from a script: podsdesktop --battery"
