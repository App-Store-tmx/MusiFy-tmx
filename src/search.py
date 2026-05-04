"""
search.py — YouTube music search via yt-dlp
"""

import subprocess
import json
import re


def _fmt_duration(seconds) -> str:
    if not seconds:
        return ""
    try:
        s = int(seconds)
        m, s = divmod(s, 60)
        h, m = divmod(m, 60)
        if h:
            return f"{h}:{m:02d}:{s:02d}"
        return f"{m}:{s:02d}"
    except Exception:
        return ""


class MusicSearch:
    def search(self, query: str, max_results: int = 15) -> list[dict]:
        """Search YouTube Music / YouTube for tracks using yt-dlp."""
        try:
            return self._ytdlp_search(query, max_results)
        except Exception as e:
            print(f"[Search] Error: {e}")
            return []

    def _ytdlp_search(self, query: str, max_results: int) -> list[dict]:
        cmd = [
            "yt-dlp",
            f"ytsearch{max_results}:{query} music",
            "--dump-json",
            "--no-playlist",
            "--flat-playlist",
            "--skip-download",
            "--no-warnings",
            "--quiet",
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        tracks = []
        for line in result.stdout.strip().splitlines():
            if not line.strip():
                continue
            try:
                data = json.loads(line)
                track = self._parse_entry(data)
                if track:
                    tracks.append(track)
            except json.JSONDecodeError:
                continue
        return tracks

    def _parse_entry(self, data: dict) -> dict | None:
        vid_id = data.get("id") or data.get("url", "")
        if not vid_id:
            return None

        title = data.get("title", "Unknown")
        channel = data.get("channel") or data.get("uploader") or "Unknown"
        duration = data.get("duration")
        thumbnails = data.get("thumbnails", [])

        # Best thumbnail
        thumb_url = ""
        if thumbnails:
            for t in reversed(thumbnails):
                url = t.get("url", "")
                if url and url.startswith("http"):
                    thumb_url = url
                    break
        if not thumb_url and vid_id:
            thumb_url = f"https://img.youtube.com/vi/{vid_id}/mqdefault.jpg"

        # Try to parse artist from title
        artist = channel
        if " - " in title:
            parts = title.split(" - ", 1)
            artist = parts[0].strip()
            title = parts[1].strip()

        # Clean up title
        title = re.sub(r'\[.*?\]|\(.*?(?:official|audio|lyric|video|hd|hq).*?\)',
                       '', title, flags=re.IGNORECASE).strip()

        return {
            "id": vid_id,
            "title": title or "Unknown",
            "artist": artist,
            "channel": channel,
            "duration": duration,
            "duration_str": _fmt_duration(duration),
            "thumbnail": thumb_url,
            "url": data.get("url") or f"https://www.youtube.com/watch?v={vid_id}",
            "webpage_url": f"https://www.youtube.com/watch?v={vid_id}",
        }

    def get_stream_url(self, track: dict) -> str | None:
        """Resolve best audio stream URL for playback."""
        vid_url = track.get("webpage_url") or track.get("url", "")
        if not vid_url:
            return None
        try:
            cmd = [
                "yt-dlp",
                "-f", "bestaudio[ext=webm]/bestaudio[ext=m4a]/bestaudio",
                "--get-url",
                "--no-warnings",
                "--quiet",
                vid_url,
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=20)
            url = result.stdout.strip().splitlines()[0] if result.stdout.strip() else None
            return url
        except Exception as e:
            print(f"[Search] Stream URL error: {e}")
            return None
