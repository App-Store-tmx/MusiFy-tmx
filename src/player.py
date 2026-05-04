"""
player.py — mpv-based audio player for Musify
Falls back to vlc if mpv is unavailable.
"""

import subprocess
import threading
import time
import os
import socket
import json
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
        self._play_token = 0
        self._is_mpv = False
        self._ipc_path = "/tmp/musify_mpv.sock"

    def set_app(self, app):
        self._app = app

    def play(self, track: dict, start_time: float = 0.0):
        """Start playing a track (checks cache, then resolves)."""
        self.stop()
        self._play_token += 1
        token = self._play_token
        self._current_track = track
        self._playing = False
        self._paused = False
        self._position = start_time
        self._duration = track.get("duration") or 0.0
        
        # Check cache first
        local_path = cache_manager.get_audio_path(track.get("id", ""))
        if local_path:
            print(f"[Player] Playing from cache: {track.get('title')}")
            self._start_mpv(local_path, track, token, start_time)
        else:
            print(f"[Player] Streaming: {track.get('title')}")
            threading.Thread(target=self._resolve_and_play, args=(track, token, start_time), daemon=True).start()

    def _resolve_and_play(self, track: dict, token: int, start_time: float):
        stream_url = self._searcher.get_stream_url(track)
        if self._play_token != token:
            return
            
        if not stream_url:
            print(f"[Player] Could not resolve stream for: {track.get('title')}")
            # If we fail to resolve, skip to next to avoid being stuck
            if self._on_track_end:
                self._on_track_end()
            return
        
        # Start playing stream
        self._start_mpv(stream_url, track, token, start_time)
        
        # Simultaneously cache in background
        cache_manager.download_audio(track)

    def _start_mpv(self, url: str, track: dict, token: int, start_time: float = 0.0):
        with self._lock:
            if self._play_token != token:
                return
            self._kill_proc()
            player_bin = self._find_player()
            if not player_bin:
                print("[Player] No supported player found (mpv or vlc).")
                return

            self._is_mpv = "mpv" in player_bin
            if self._is_mpv:
                cmd = [
                    player_bin,
                    "--no-video",
                    "--no-terminal",
                    f"--volume={self._volume}",
                    f"--input-ipc-server={self._ipc_path}",
                ]
                if start_time > 0:
                    cmd.append(f"--start={start_time}")
                cmd.append(url)
            else:  # vlc
                cmd = [
                    player_bin,
                    "-I", "dummy",
                    "--no-video",
                    f"--gain={self._volume/100:.2f}",
                ]
                if start_time > 0:
                    cmd.append(f"--start-time={start_time}")
                cmd.append(url)
                cmd.append("vlc://quit")

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
            target=self._monitor, args=(token,), daemon=True)
        self._monitor_thread.start()

        self._position_thread = threading.Thread(
            target=self._track_position, args=(token, start_time), daemon=True)
        self._position_thread.start()

    def _monitor(self, token: int):
        proc = self._proc
        if proc:
            proc.wait()
            
        # Only trigger track end if this track wasn't manually stopped/skipped
        if self._play_token == token:
            self._playing = False
            self._position = 0.0
            if self._on_track_end:
                self._on_track_end()

    def _track_position(self, token: int, start_time: float):
        start_wall = time.time()
        while self._play_token == token and self._playing and self._proc and self._proc.poll() is None:
            if not self._paused:
                self._position = start_time + (time.time() - start_wall)
            else:
                start_wall = time.time() - (self._position - start_time)
            time.sleep(0.5)

    def stop(self):
        # Increment token so monitor thread drops old session
        self._play_token += 1
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

    def seek(self, target_time: float):
        if self._current_track:
            self.play(self._current_track, start_time=target_time)

    def is_playing(self) -> bool:
        return self._playing and not self._paused

    def set_volume(self, vol: int):
        self._volume = max(0, min(100, vol))
        if self._is_mpv and self._playing and os.path.exists(self._ipc_path):
            try:
                msg = json.dumps({"command": ["set_property", "volume", self._volume]}) + "\n"
                with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as client:
                    client.connect(self._ipc_path)
                    client.sendall(msg.encode())
            except Exception:
                pass # Silently fail if IPC connection fails

    def get_position(self) -> tuple[float, float]:
        return self._position, self._duration

    def next(self):
        self.stop()
        if self._on_next:
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
