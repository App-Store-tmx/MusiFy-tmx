#!/data/data/com.termux/files/usr/bin/bash

echo "Uninstalling Musify..."

APP_DIR="$HOME/.local/opt/musify"
BIN_DIR="$PREFIX/bin"
APP_MENU_DIR="$HOME/.local/share/applications"

rm -rf "$APP_DIR"
rm -f  "$BIN_DIR/musify"
rm -f  "$APP_MENU_DIR/musify.desktop"

update-desktop-database "$APP_MENU_DIR" 2>/dev/null || true

echo "Musify uninstalled."
