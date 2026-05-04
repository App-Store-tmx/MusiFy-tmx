"""
player.py — mpv-based audio player for Musify
Falls back to vlc if mpv is unavailable.
"""

import subprocess
import threading
import time
import os
from src.search import MusicSearch
from src.cache import cache_manager


class MusicPlayer:
    def __init__(self, on_track_end=None, on_next=None):
        self._proc: subprocess.Popen | None = None
        self._lock = threading.Lock()
        self._on_track_end = on_track_end
        self._on_next = on_next
        self._volume = 80
        self._paused = False
        self._playing = False
        self._position = 0.0
        self._duration = 0.0
        self._current_track: dict | None = None
        self._app = None
        self._searcher = MusicSearch()
        self._monitor_thread: threading.Thread | None = None
        self._position_thread: threading.Thread | None = None

    def set_app(self, app):
        self._app = app

    def play(self, track: dict):
        """Start playing a track (checks cache, then resolves)."""
        self.stop()
        self._current_track = track
        self._playing = False
        self._paused = False
        self._position = 0.0
        self._duration = track.get("duration") or 0.0
        
        # Check cache first
        local_path = cache_manager.get_audio_path(track.get("id", ""))
        if local_path:
            print(f"[Player] Playing from cache: {track.get('title')}")
            self._start_mpv(local_path, track)
        else:
            print(f"[Player] Streaming: {track.get('title')}")
            threading.Thread(target=self._resolve_and_play, args=(track,), daemon=True).start()

    def _resolve_and_play(self, track: dict):
        stream_url = self._searcher.get_stream_url(track)
        if not stream_url:
            print(f"[Player] Could not resolve stream for: {track.get('title')}")
            return
        
        # Start playing stream
        self._start_mpv(stream_url, track)
        
        # Simultaneously cache in background
        cache_manager.download_audio(track)

    def _start_mpv(self, url: str, track: dict):
        with self._lock:
            self._kill_proc()
            player_bin = self._find_player()
            if not player_bin:
                print("[Player] No supported player found (mpv or vlc).")
                return

            if "mpv" in player_bin:
                cmd = [
                    player_bin,
                    "--no-video",
                    "--no-terminal",
                    f"--volume={self._volume}",
                    url,
                ]
            else:  # vlc
                cmd = [
                    player_bin,
                    "-I", "dummy",
                    "--no-video",
                    f"--gain={self._volume/100:.2f}",
                    url,
                    "vlc://quit",
                ]

            try:
                self._proc = subprocess.Popen(
                    cmd,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
                self._playing = True
                self._paused = False
            except Exception as e:
                print(f"[Player] Launch error: {e}")
                return

        self._monitor_thread = threading.Thread(
            target=self._monitor, daemon=True)
        self._monitor_thread.start()

        self._position_thread = threading.Thread(
            target=self._track_position, daemon=True)
        self._position_thread.start()

    def _monitor(self):
        proc = self._proc
        if proc:
            proc.wait()
        self._playing = False
        self._position = 0.0
        if self._on_track_end:
            self._on_track_end()

    def _track_position(self):
        start = time.time()
        while self._playing and self._proc and self._proc.poll() is None:
            if not self._paused:
                self._position = time.time() - start
            time.sleep(0.5)

    def stop(self):
        with self._lock:
            self._kill_proc()
        self._playing = False
        self._paused = False

    def pause(self):
        if self._proc and self._playing and not self._paused:
            try:
                import signal
                self._proc.send_signal(signal.SIGSTOP)
                self._paused = True
            except Exception:
                pass

    def resume(self):
        if self._proc and self._paused:
            try:
                import signal
                self._proc.send_signal(signal.SIGCONT)
                self._paused = False
            except Exception:
                pass

    def is_playing(self) -> bool:
        return self._playing and not self._paused

    def set_volume(self, vol: int):
        self._volume = max(0, min(100, vol))

    def get_position(self) -> tuple[float, float]:
        return self._position, self._duration

    def next(self):
        if self._on_next:
            self.stop()
            self._on_next()

    def prev(self):
        """Restart current track (or go prev via app callback)."""
        track = self._current_track
        if track:
            self.play(track)

    def _kill_proc(self):
        if self._proc:
            try:
                self._proc.terminate()
                self._proc.wait(timeout=2)
            except Exception:
                try:
                    self._proc.kill()
                except Exception:
                    pass
            self._proc = None

    @staticmethod
    def _find_player() -> str | None:
        for bin_name in ("mpv", "vlc", "cvlc"):
            result = subprocess.run(["which", bin_name],
                                    capture_output=True, text=True)
            if result.returncode == 0:
                return result.stdout.strip()
        return None
