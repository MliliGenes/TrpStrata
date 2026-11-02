#!/usr/bin/env bash
# Remove trpStrata and put your desktop back the way it was.
set -uo pipefail
APP=io.github.TrpStrata
DEST="$HOME/.local/share/trpstrata"
cd "$(dirname "$(readlink -f "$0")")"
PYTHON=/usr/bin/python3
HELPER=$("$PYTHON" -m trp_strata.install_storage helper-pattern)

if [ "$(readlink "$HOME/.local/bin/ws" 2>/dev/null || true)" = "$DEST/trpstrata" ]; then
	rm -f "$HOME/.local/bin/ws"
fi

if [ -x "$DEST/trpstrata" ]; then
	"$DEST/trpstrata" restore || exit 1
else
	"$PYTHON" -m trp_strata restore || exit 1
fi
pkill -f "$HELPER" 2>/dev/null
"$PYTHON" -m trp_strata.install_storage uninstall || exit 1
CONFIG_DIR=$("$PYTHON" -c 'from trp_strata.storage import CONFIG_DIR; print(CONFIG_DIR)')
rm -rf "$CONFIG_DIR"
rm -f "$HOME/.local/bin/trpstrata" "$HOME/.local/share/applications/$APP.desktop" \
	"$HOME/.local/share/icons/hicolor/scalable/apps/$APP.svg" "$HOME/.config/autostart/trpstrata-desktop.desktop"
for size in 16 24 32 48 64 128 256 512; do
	rm -f "$HOME/.local/share/icons/hicolor/${size}x${size}/apps/$APP.png"
done
gtk-update-icon-cache -q -t "$HOME/.local/share/icons/hicolor" 2>/dev/null || true
echo "trpStrata removed. (The adw-gtk3 theme in ~/.local/share/themes was left in place.)"
