#!/data/data/com.termux/files/usr/bin/bash
export DISPLAY=:0
cd "$HOME/.local/opt/musify"
python3 main.py "$@"
