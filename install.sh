#!/data/data/com.termux/files/usr/bin/bash
set -e

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  Musify Installer v1.0.0"
echo "  Compact Music Streaming for Termux Desktop"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

APP_DIR="$HOME/.local/opt/musify"
BIN_DIR="$PREFIX/bin"
APP_MENU_DIR="$HOME/.local/share/applications"

echo ""
echo "[1/5] Updating packages..."
pkg update -y

echo ""
echo "[2/5] Installing system packages..."
pkg install -y python python-tkinter mpv ffmpeg

echo ""
echo "[3/5] Installing Python dependencies..."
pip install customtkinter Pillow yt-dlp --break-system-packages

echo ""
echo "[4/5] Setting up Musify..."
mkdir -p "$APP_DIR/src"
mkdir -p "$APP_MENU_DIR"

# Copy app files
cp main.py        "$APP_DIR/"
cp requirements.txt "$APP_DIR/"
cp -r src/        "$APP_DIR/"

# Generate icon via Python Pillow
python3 - <<'PYEOF'
import os, sys
from PIL import Image, ImageDraw, ImageFont

app_dir = os.path.expandvars("$HOME/.local/opt/musify")
os.makedirs(app_dir, exist_ok=True)

# Icon: dark circle with green play button
img = Image.new("RGBA", (256, 256), (0, 0, 0, 0))
d = ImageDraw.Draw(img)

# Outer circle
d.ellipse([4, 4, 252, 252], fill="#0f0f0f")
d.ellipse([2, 2, 254, 254], outline="#1db954", width=6)

# Music note symbol
cx, cy = 128, 128
# Play triangle
pts = [(cx-38, cy-46), (cx+42, cy), (cx-38, cy+46)]
d.polygon(pts, fill="#1db954")

img.save(os.path.join(app_dir, "icon.png"))
print("  ✓ Icon generated")

# Screenshot placeholder
shot = Image.new("RGB", (640, 480), "#0f0f0f")
d2 = ImageDraw.Draw(shot)
d2.rectangle([0, 0, 640, 52], fill="#111111")
d2.text((16, 16), "🎵 Musify", fill="#1db954")
d2.rectangle([8, 70, 632, 130], fill="#1a1a1a")
d2.rectangle([8, 140, 632, 200], fill="#1a1a1a")
d2.rectangle([8, 210, 632, 270], fill="#1a1a1a")
d2.rectangle([0, 408, 640, 480], fill="#111111")
d2.ellipse([275, 415, 365, 472], fill="#1db954")
shot.save(os.path.join(app_dir, "screenshot.png"))
print("  ✓ Screenshot generated")
PYEOF

echo ""
echo "[5/5] Creating launch scripts & desktop entry..."

# Launch script
cat > "$APP_DIR/launch.sh" << 'EOF'
#!/data/data/com.termux/files/usr/bin/bash
export DISPLAY=:0
cd "$HOME/.local/opt/musify"
python3 main.py "$@"
EOF
chmod +x "$APP_DIR/launch.sh"

# Uninstall script
cp uninstall.sh "$APP_DIR/"
chmod +x "$APP_DIR/uninstall.sh"

# Global CLI command
cat > "$BIN_DIR/musify" << 'EOF'
#!/data/data/com.termux/files/usr/bin/bash
export DISPLAY=:0
cd "$HOME/.local/opt/musify"
python3 main.py "$@"
EOF
chmod +x "$BIN_DIR/musify"

# Desktop entry
cat > "$APP_MENU_DIR/musify.desktop" << EOF
[Desktop Entry]
Version=1.0
Type=Application
Name=Musify
Comment=Compact Music Streaming App
Exec=$APP_DIR/launch.sh
Icon=$APP_DIR/icon.png
Categories=Audio;Music;Player;
Terminal=false
StartupNotify=true
EOF

update-desktop-database "$APP_MENU_DIR" 2>/dev/null || true

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  ✓ Musify installed!"
echo "  Run:   musify"
echo "  Menu:  Audio → Musify"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
