"""
cache.py — Disk cache manager for Musify
Handles audio and thumbnail caching.
"""

import os
import hashlib
import urllib.request
from PIL import Image
import io
import subprocess

CACHE_DIR = os.path.expanduser("~/.cache/musify")
AUDIO_DIR = os.path.join(CACHE_DIR, "audio")
THUMB_DIR = os.path.join(CACHE_DIR, "thumbs")

class CacheManager:
    def __init__(self):
        os.makedirs(AUDIO_DIR, exist_ok=True)
        os.makedirs(THUMB_DIR, exist_ok=True)

    def _get_id_hash(self, track_id: str) -> str:
        return hashlib.md5(track_id.encode()).hexdigest()

    def get_audio_path(self, track_id: str) -> str | None:
        """Return path to cached audio file if it exists."""
        # We try a few common extensions that yt-dlp might use
        for ext in ["m4a", "webm", "mp3", "opus"]:
            path = os.path.join(AUDIO_DIR, f"{track_id}.{ext}")
            if os.path.exists(path) and os.path.getsize(path) > 1024: # > 1KB
                return path
        return None

    def download_audio(self, track: dict):
        """Download audio to cache in background using yt-dlp."""
        track_id = track.get("id")
        url = track.get("webpage_url") or track.get("url")
        if not track_id or not url:
            return

        # Check if already downloading or exists
        if self.get_audio_path(track_id):
            return

        # Target path: use .m4a as preferred format for compatibility
        out_tmpl = os.path.join(AUDIO_DIR, f"{track_id}.%(ext)s")
        
        cmd = [
            "yt-dlp",
            "-f", "bestaudio[ext=m4a]/bestaudio",
            "-o", out_tmpl,
            "--no-playlist",
            "--quiet",
            "--no-warnings",
            url
        ]
        
        # We run this in a separate process/thread normally
        try:
            subprocess.Popen(cmd, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except Exception as e:
            print(f"[Cache] Download error: {e}")

    def get_thumb_path(self, url: str) -> str:
        url_hash = hashlib.md5(url.encode()).hexdigest()
        return os.path.join(THUMB_DIR, f"{url_hash}.png")

    def fetch_thumbnail(self, url: str):
        """Fetch and cache thumbnail. Returns PIL Image or None."""
        if not url: return None
        
        path = self.get_thumb_path(url)
        if os.path.exists(path):
            try:
                return Image.open(path)
            except Exception:
                pass

        try:
            with urllib.request.urlopen(url, timeout=5) as r:
                data = r.read()
            img = Image.open(io.BytesIO(data)).convert("RGBA")
            img.save(path, "PNG")
            return img
        except Exception as e:
            print(f"[Cache] Thumb error: {e}")
            return None

cache_manager = CacheManager()
