"""
Musify — Compact Music Streaming App for Termux Desktop
CustomTkinter + yt-dlp + mpv
"""

import customtkinter as ctk
import threading
import subprocess
import os
import sys
import json
import time
import urllib.request
import io
from PIL import Image, ImageDraw, ImageFilter
from src.search import MusicSearch
from src.player import MusicPlayer

# ── Theme ──────────────────────────────────────────────────────────────────────
DARK_BG     = "#0f0f0f"
CARD_BG     = "#1a1a1a"
CARD_HOVER  = "#242424"
ACCENT      = "#1db954"        # Spotify green
ACCENT_DIM  = "#158a3e"
TEXT_PRI    = "#ffffff"
TEXT_SEC    = "#a8a8a8"
TEXT_DIM    = "#555555"
BORDER      = "#2a2a2a"
PLAYER_BG   = "#111111"

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("green")

# ── Helpers ────────────────────────────────────────────────────────────────────

def fetch_thumbnail(url: str, size=(54, 54)) -> ctk.CTkImage | None:
    try:
        with urllib.request.urlopen(url, timeout=5) as r:
            data = r.read()
        img = Image.open(io.BytesIO(data)).convert("RGBA").resize(size, Image.LANCZOS)
        return ctk.CTkImage(light_image=img, dark_image=img, size=size)
    except Exception:
        return None

def make_placeholder(size=(54, 54), color="#1a1a1a") -> ctk.CTkImage:
    img = Image.new("RGBA", size, color)
    d = ImageDraw.Draw(img)
    cx, cy = size[0]//2, size[1]//2
    r = min(size)//4
    d.ellipse([cx-r, cy-r, cx+r, cy+r], fill="#2a2a2a")
    arrow_pts = [(cx-r//2, cy-r//3), (cx+r//2, cy), (cx-r//2, cy+r//3)]
    d.polygon(arrow_pts, fill="#555555")
    return ctk.CTkImage(light_image=img, dark_image=img, size=size)

def make_icon_img(size=(96, 96)) -> ctk.CTkImage:
    img = Image.new("RGBA", size, "#0f0f0f")
    d = ImageDraw.Draw(img)
    d.ellipse([4, 4, size[0]-4, size[1]-4], fill=ACCENT)
    cx, cy = size[0]//2, size[1]//2
    r = size[0]//4
    pts = [(cx-r, cy-int(r*1.1)), (cx+r, cy), (cx-r, cy+int(r*1.1))]
    d.polygon(pts, fill="#0f0f0f")
    return ctk.CTkImage(light_image=img, dark_image=img, size=size)


# ── Track Card ────────────────────────────────────────────────────────────────

class TrackCard(ctk.CTkFrame):
    def __init__(self, parent, track: dict, on_play, row_idx: int):
        super().__init__(parent, fg_color=CARD_BG, corner_radius=8,
                         border_width=1, border_color=BORDER)
        self.track = track
        self.on_play = on_play
        self._thumb_job = None

        self.grid_columnconfigure(1, weight=1)
        self.configure(cursor="hand2")

        # Thumbnail
        self.thumb_lbl = ctk.CTkLabel(self, text="", width=54, height=54,
                                       image=make_placeholder())
        self.thumb_lbl.grid(row=0, column=0, padx=(8,10), pady=8)

        # Info
        info = ctk.CTkFrame(self, fg_color="transparent")
        info.grid(row=0, column=1, sticky="ew", pady=4)
        info.grid_columnconfigure(0, weight=1)

        title = track.get("title", "Unknown")[:55]
        artist = track.get("artist", track.get("channel", "Unknown"))[:40]
        dur = track.get("duration_str", "")

        self.title_lbl = ctk.CTkLabel(info, text=title, font=("Inter", 12, "bold"),
                                       text_color=TEXT_PRI, anchor="w")
        self.title_lbl.grid(row=0, column=0, sticky="ew")

        self.artist_lbl = ctk.CTkLabel(info, text=artist, font=("Inter", 10),
                                        text_color=TEXT_SEC, anchor="w")
        self.artist_lbl.grid(row=1, column=0, sticky="ew")

        # Duration + play
        right = ctk.CTkFrame(self, fg_color="transparent", width=80)
        right.grid(row=0, column=2, padx=(4,8))

        ctk.CTkLabel(right, text=dur, font=("Inter", 10),
                     text_color=TEXT_DIM).pack(pady=(8,2))

        self.play_btn = ctk.CTkButton(right, text="▶", width=32, height=22,
                                       font=("Inter", 11), fg_color=ACCENT,
                                       hover_color=ACCENT_DIM, corner_radius=4,
                                       command=self._play)
        self.play_btn.pack()

        for w in (self, self.thumb_lbl, info, self.title_lbl, self.artist_lbl):
            w.bind("<Button-1>", lambda e: self._play())

        threading.Thread(target=self._load_thumb, daemon=True).start()

    def _load_thumb(self):
        url = self.track.get("thumbnail", "")
        if url:
            img = fetch_thumbnail(url)
            if img:
                self.after(0, lambda: self.thumb_lbl.configure(image=img))

    def _play(self):
        self.on_play(self.track)

    def set_active(self, active: bool):
        color = CARD_HOVER if active else CARD_BG
        border = ACCENT if active else BORDER
        self.configure(fg_color=color, border_color=border)
        self.play_btn.configure(text="■" if active else "▶")


# ── Mini Player Bar ───────────────────────────────────────────────────────────

class PlayerBar(ctk.CTkFrame):
    def __init__(self, parent, player: MusicPlayer):
        super().__init__(parent, fg_color=PLAYER_BG, height=72, corner_radius=0,
                         border_width=1, border_color=BORDER)
        self.player = player
        self.pack_propagate(False)
        self.grid_columnconfigure(1, weight=1)

        # Thumb
        self.thumb = ctk.CTkLabel(self, text="", width=48, height=48,
                                   image=make_placeholder((48,48)))
        self.thumb.grid(row=0, column=0, padx=(12,10), pady=12)

        # Track info
        info = ctk.CTkFrame(self, fg_color="transparent")
        info.grid(row=0, column=1, sticky="ew")
        info.grid_columnconfigure(0, weight=1)

        self.title_var = ctk.StringVar(value="Nothing playing")
        self.artist_var = ctk.StringVar(value="Search and select a track")

        ctk.CTkLabel(info, textvariable=self.title_var, font=("Inter", 12, "bold"),
                     text_color=TEXT_PRI, anchor="w").grid(row=0, column=0, sticky="ew")
        ctk.CTkLabel(info, textvariable=self.artist_var, font=("Inter", 10),
                     text_color=TEXT_SEC, anchor="w").grid(row=1, column=0, sticky="ew")

        # Progress
        self.progress = ctk.CTkProgressBar(info, height=3, fg_color=BORDER,
                                            progress_color=ACCENT)
        self.progress.set(0)
        self.progress.grid(row=2, column=0, sticky="ew", pady=(4,0))

        # Controls
        ctrl = ctk.CTkFrame(self, fg_color="transparent")
        ctrl.grid(row=0, column=2, padx=12)

        btn_cfg = dict(width=36, height=36, font=("Inter", 14),
                       fg_color="transparent", hover_color=CARD_HOVER,
                       text_color=TEXT_SEC, corner_radius=18)

        self.prev_btn = ctk.CTkButton(ctrl, text="⏮", **btn_cfg, command=self._prev)
        self.prev_btn.grid(row=0, column=0, padx=2)

        self.play_btn = ctk.CTkButton(ctrl, text="▶", width=42, height=42,
                                       font=("Inter", 16), fg_color=ACCENT,
                                       hover_color=ACCENT_DIM, corner_radius=21,
                                       text_color="#000000", command=self._toggle)
        self.play_btn.grid(row=0, column=1, padx=4)

        self.next_btn = ctk.CTkButton(ctrl, text="⏭", **btn_cfg, command=self._next)
        self.next_btn.grid(row=0, column=2, padx=2)

        # Volume
        vol = ctk.CTkFrame(self, fg_color="transparent", width=130)
        vol.grid(row=0, column=3, padx=(0,16))

        ctk.CTkLabel(vol, text="🔊", font=("Inter", 13),
                     text_color=TEXT_DIM).pack(side="left")
        self.vol_slider = ctk.CTkSlider(vol, width=80, height=12,
                                         fg_color=BORDER, progress_color=ACCENT,
                                         button_color=TEXT_SEC, from_=0, to=100,
                                         command=self._vol_change)
        self.vol_slider.set(80)
        self.vol_slider.pack(side="left", padx=4)

        self._update_loop()

    def update_track(self, track: dict):
        self.title_var.set(track.get("title","")[:45])
        self.artist_var.set(track.get("artist", track.get("channel",""))[:35])
        url = track.get("thumbnail","")
        if url:
            threading.Thread(target=self._load_thumb, args=(url,), daemon=True).start()

    def _load_thumb(self, url):
        img = fetch_thumbnail(url, (48,48))
        if img:
            self.after(0, lambda: self.thumb.configure(image=img))

    def _toggle(self):
        if self.player.is_playing():
            self.player.pause()
            self.play_btn.configure(text="▶")
        else:
            self.player.resume()
            self.play_btn.configure(text="⏸")

    def _prev(self): self.player.prev()
    def _next(self): self.player.next()

    def _vol_change(self, v):
        self.player.set_volume(int(v))

    def set_playing(self, playing: bool):
        self.play_btn.configure(text="⏸" if playing else "▶")

    def _update_loop(self):
        pos, dur = self.player.get_position()
        if dur > 0:
            self.progress.set(pos / dur)
        self.after(500, self._update_loop)


# ── Search Page ───────────────────────────────────────────────────────────────

class SearchPage(ctk.CTkFrame):
    def __init__(self, parent, on_play):
        super().__init__(parent, fg_color=DARK_BG, corner_radius=0)
        self.on_play = on_play
        self.searcher = MusicSearch()
        self.cards: list[TrackCard] = []
        self.active_card: TrackCard | None = None
        self._search_thread = None

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)

        # ── Header ──
        hdr = ctk.CTkFrame(self, fg_color="transparent")
        hdr.grid(row=0, column=0, sticky="ew", padx=16, pady=(14,8))
        hdr.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(hdr, text="🎵 Musify", font=("Inter", 18, "bold"),
                     text_color=ACCENT).grid(row=0, column=0, sticky="w")

        search_row = ctk.CTkFrame(hdr, fg_color="transparent")
        search_row.grid(row=1, column=0, sticky="ew", pady=(8,0))
        search_row.grid_columnconfigure(0, weight=1)

        self.search_var = ctk.StringVar()
        self.search_entry = ctk.CTkEntry(
            search_row, textvariable=self.search_var,
            placeholder_text="Search songs, artists…",
            font=("Inter", 12), height=36,
            fg_color=CARD_BG, border_color=BORDER,
            border_width=1, corner_radius=8, text_color=TEXT_PRI)
        self.search_entry.grid(row=0, column=0, sticky="ew")
        self.search_entry.bind("<Return>", self._search)

        self.search_btn = ctk.CTkButton(
            search_row, text="Search", width=82, height=36,
            font=("Inter", 12), fg_color=ACCENT, hover_color=ACCENT_DIM,
            corner_radius=8, text_color="#000", command=self._search)
        self.search_btn.grid(row=0, column=1, padx=(8,0))

        # ── Results scroll ──
        self.scroll = ctk.CTkScrollableFrame(self, fg_color=DARK_BG,
                                              scrollbar_button_color=BORDER)
        self.scroll.grid(row=1, column=0, sticky="nsew", padx=8, pady=(0,4))
        self.scroll.grid_columnconfigure(0, weight=1)

        self._show_welcome()

    def _show_welcome(self):
        for c in self.cards: c.destroy()
        self.cards.clear()

        msg = ctk.CTkLabel(self.scroll,
                           text="Search for music to start streaming ♪",
                           font=("Inter", 13), text_color=TEXT_DIM)
        msg.grid(row=0, column=0, pady=60)
        self._welcome_lbl = msg

    def _search(self, *_):
        q = self.search_var.get().strip()
        if not q: return
        if self._search_thread and self._search_thread.is_alive(): return

        for c in self.cards: c.destroy()
        self.cards.clear()
        if hasattr(self, "_welcome_lbl"):
            self._welcome_lbl.destroy()

        self.loading = ctk.CTkLabel(self.scroll, text="Searching…",
                                     font=("Inter", 12), text_color=TEXT_DIM)
        self.loading.grid(row=0, column=0, pady=40)

        self.search_btn.configure(state="disabled", text="…")
        self._search_thread = threading.Thread(
            target=self._do_search, args=(q,), daemon=True)
        self._search_thread.start()

    def _do_search(self, q: str):
        results = self.searcher.search(q, max_results=15)
        self.after(0, lambda: self._show_results(results))

    def _show_results(self, results: list):
        self.loading.destroy()
        self.search_btn.configure(state="normal", text="Search")

        if not results:
            ctk.CTkLabel(self.scroll, text="No results found.",
                         font=("Inter", 12), text_color=TEXT_DIM
                         ).grid(row=0, column=0, pady=40)
            return

        for i, track in enumerate(results):
            card = TrackCard(self.scroll, track, self._on_play, i)
            card.grid(row=i, column=0, sticky="ew", padx=4, pady=3)
            self.cards.append(card)

    def _on_play(self, track: dict):
        for c in self.cards:
            c.set_active(c.track is track)
        self.on_play(track, playlist=self.cards)

    def mark_active(self, track: dict | None):
        for c in self.cards:
            c.set_active(track is not None and c.track is track)


# ── Main Window ───────────────────────────────────────────────────────────────

class MusifyApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Musify")
        self.geometry("640x680")
        self.minsize(500, 500)
        self.configure(fg_color=DARK_BG)

        icon = make_icon_img((96,96))
        try:
            # Set window icon via PIL
            raw = icon._light_image
            self.iconphoto(True, self._pil_to_tk(raw))
        except Exception:
            pass

        self.player = MusicPlayer(on_track_end=self._on_track_end,
                                   on_next=self._on_next_track)
        self.current_track: dict | None = None
        self.playlist: list[TrackCard] = []

        self.grid_rowconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=0)
        self.grid_columnconfigure(0, weight=1)

        self.search_page = SearchPage(self, on_play=self._play_track)
        self.search_page.grid(row=0, column=0, sticky="nsew")

        self.player_bar = PlayerBar(self, self.player)
        self.player_bar.grid(row=1, column=0, sticky="ew")

        self.player.set_app(self)
        self.protocol("WM_DELETE_WINDOW", self._quit)

    def _pil_to_tk(self, pil_img):
        import tkinter as tk
        from PIL import ImageTk
        return ImageTk.PhotoImage(pil_img)

    def _play_track(self, track: dict, playlist: list[TrackCard] = None):
        self.current_track = track
        if playlist:
            self.playlist = playlist
        self.player_bar.update_track(track)
        self.player_bar.set_playing(True)
        self.player.play(track)

    def _on_track_end(self):
        self.after(0, self._auto_next)

    def _auto_next(self):
        if not self.playlist or self.current_track is None:
            return
        tracks = [c.track for c in self.playlist]
        try:
            idx = tracks.index(self.current_track)
            next_idx = (idx + 1) % len(tracks)
            next_track = tracks[next_idx]
            self._play_track(next_track)
            self.search_page.mark_active(next_track)
        except (ValueError, IndexError):
            pass

    def _on_next_track(self):
        self._auto_next()

    def _quit(self):
        self.player.stop()
        self.destroy()


def main():
    app = MusifyApp()
    app.mainloop()


if __name__ == "__main__":
    main()
