#!/usr/bin/env bash
# Remove trpStrata and put your desktop back the way it was.
set -euo pipefail
APP=io.github.TrpStrata
DEST="$HOME/.local/share/trpstrata"
cd "$(dirname "$(readlink -f "$0")")"
PYTHON=/usr/bin/python3
HELPER=$("$PYTHON" -m trp_strata.install_storage helper-pattern)
CONFIG_DIR=$("$PYTHON" -c 'from trp_strata.storage import CONFIG_DIR; print(CONFIG_DIR)')

for name in ws wallpaper-studio; do
	case "$(readlink "$HOME/.local/bin/$name" 2>/dev/null || true)" in
		"$DEST/trpstrata"|"$HOME/.local/share/wallpaper-studio/wallpaper-studio")
			rm -f "$HOME/.local/bin/$name" ;;
	esac
done

if [ -x "$DEST/trpstrata" ]; then
	"$DEST/trpstrata" restore || exit 1
else
	"$PYTHON" -m trp_strata restore || exit 1
fi
# Refresh the greeter from the restored settings before removing its snapshot.
"$PYTHON" -c 'from trp_strata.native_wallpaper import NativeWallpaper; NativeWallpaper().refresh_lock_screen()'
pkill -f "$HELPER" 2>/dev/null || true
rm -rf "$CONFIG_DIR"
rm -f "$HOME/.local/bin/trpstrata" "$HOME/.local/share/applications/$APP.desktop" \
	"$HOME/.local/share/icons/hicolor/scalable/apps/$APP.svg" "$HOME/.config/autostart/trpstrata-desktop.desktop"
for size in 16 24 32 48 64 128 256 512; do
	rm -f "$HOME/.local/share/icons/hicolor/${size}x${size}/apps/$APP.png"
done
gtk-update-icon-cache -q -t "$HOME/.local/share/icons/hicolor" 2>/dev/null || true
# Load the removal module before deleting the installed Python package. Nothing
# after this exec may depend on the script or package still existing on disk.
exec "$PYTHON" -c 'from trp_strata.install_storage import uninstall; from trp_strata.storage import PATHS; uninstall(PATHS); print("trpStrata removed. Shared themes and the personal GNOME profile were retained.")'
