"""
replay_page.py
--------------
Tkinter page for replaying a past interview session.
Features: play/pause/seek scrubber, animated metric gauges,
transcript replay, and audio playback (if WAV exists).
"""

import tkinter as tk
from tkinter import ttk, messagebox
from typing import Optional, Dict, Callable
import time

from replay_manager import ReplayManager
from database_manager import DatabaseManager

PAL = {
    "bg":     "#0D1117",
    "card":   "#161B22",
    "border": "#30363D",
    "accent": "#00D4FF",
    "green":  "#3FB950",
    "orange": "#F78166",
    "yellow": "#E3B341",
    "text":   "#C9D1D9",
    "gray":   "#8B949E",
    "white":  "#FFFFFF",
}

FONT_H2   = ("Helvetica", 14, "bold")
FONT_H3   = ("Helvetica", 11, "bold")
FONT_BODY = ("Helvetica", 10)
FONT_MONO = ("Courier",   10)
FONT_SM   = ("Helvetica",  8)


class MiniGauge(tk.Canvas):
    """Compact arc gauge for replay metric display."""

    def __init__(self, parent, label="", size=80, **kw):
        super().__init__(parent, width=size, height=size,
                         bg=parent["bg"], highlightthickness=0, **kw)
        self._size  = size
        self._label = label
        self._draw(0)

    def set_value(self, v: float):
        self._draw(max(0.0, min(100.0, float(v))))

    def _draw(self, v: float):
        self.delete("all")
        s, p = self._size, 10
        col = PAL["green"] if v >= 75 else PAL["yellow"] if v >= 50 else PAL["orange"]
        self.create_arc(p, p, s-p, s-p, start=0, extent=360,
                        outline=PAL["border"], width=6, style="arc")
        self.create_arc(p, p, s-p, s-p,
                        start=135, extent=-(v / 100 * 270),
                        outline=col, width=6, style="arc")
        self.create_text(s//2, s//2 - 6, text=f"{v:.0f}",
                         font=("Helvetica", int(s * 0.18), "bold"),
                         fill=PAL["white"])
        self.create_text(s//2, s//2 + 12, text=self._label,
                         font=("Helvetica", int(s * 0.10)), fill=PAL["gray"])


class ReplayPage(tk.Frame):
    """
    Full replay interface. Integrates with ReplayManager for timed playback.
    Load a session by calling load_interview(interview_id).
    """

    def __init__(
        self,
        parent,
        db: DatabaseManager,
        **kw
    ):
        super().__init__(parent, bg=PAL["bg"], **kw)
        self.db      = db
        self._replay = ReplayManager(
            on_tick       = self._on_tick,
            on_transcript = self._on_transcript,
            on_complete   = self._on_complete,
        )
        self._duration   = 0.0
        self._scrub_drag = False
        self._build()

    # ─── Build ────────────────────────────────────────────────────────────────

    def _build(self):
        # ── Top bar ──────────────────────────────────────────────────────────
        top = tk.Frame(self, bg=PAL["card"], padx=14, pady=10)
        top.pack(fill=tk.X)
        tk.Label(top, text="Interview Replay",
                 font=FONT_H2, fg=PAL["accent"], bg=PAL["card"]).pack(side=tk.LEFT)

        self._session_label = tk.Label(
            top, text="No session loaded",
            font=FONT_BODY, fg=PAL["gray"], bg=PAL["card"]
        )
        self._session_label.pack(side=tk.LEFT, padx=20)

        # ── Body ──────────────────────────────────────────────────────────────
        body = tk.Frame(self, bg=PAL["bg"])
        body.pack(fill=tk.BOTH, expand=True, padx=16, pady=10)

        # Gauges
        gauge_frame = tk.Frame(body, bg=PAL["card"], padx=14, pady=12)
        gauge_frame.pack(fill=tk.X, pady=(0, 10))
        tk.Label(gauge_frame, text="Live Metrics",
                 font=FONT_H3, fg=PAL["accent"], bg=PAL["card"]).pack(anchor="w")

        gauges_row = tk.Frame(gauge_frame, bg=PAL["card"])
        gauges_row.pack(fill=tk.X, pady=6)
        self._gauges: Dict[str, MiniGauge] = {}
        for key, label in [
            ("overall_score",       "Overall"),
            ("confidence_score",    "Confidence"),
            ("eye_contact_score",   "Eye Contact"),
            ("speech_score",        "Speech"),
        ]:
            g = MiniGauge(gauges_row, label=label, size=88)
            g.pack(side=tk.LEFT, padx=12)
            self._gauges[key] = g

        # Text metrics row
        metrics_row = tk.Frame(gauge_frame, bg=PAL["card"])
        metrics_row.pack(fill=tk.X, pady=(4, 0))
        self._text_metrics: Dict[str, tk.Label] = {}
        for key, display in [
            ("words_per_minute", "WPM"),
            ("eye_contact_pct",  "Eye Contact %"),
            ("filler_word_count","Filler Words"),
            ("pause_count",      "Pauses"),
        ]:
            f = tk.Frame(metrics_row, bg=PAL["card"])
            f.pack(side=tk.LEFT, padx=16)
            tk.Label(f, text=display, font=FONT_SM,
                     fg=PAL["gray"], bg=PAL["card"]).pack()
            lbl = tk.Label(f, text="—", font=("Helvetica", 11, "bold"),
                           fg=PAL["accent"], bg=PAL["card"])
            lbl.pack()
            self._text_metrics[key] = lbl

        # Transcript area
        trans_card = tk.Frame(body, bg=PAL["card"], padx=10, pady=8,
                              highlightthickness=1,
                              highlightbackground=PAL["border"])
        trans_card.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
        tk.Label(trans_card, text="Transcript",
                 font=FONT_H3, fg=PAL["accent"], bg=PAL["card"]).pack(anchor="w")

        self._trans_text = tk.Text(
            trans_card, bg=PAL["bg"], fg=PAL["text"],
            font=FONT_MONO, relief="flat",
            height=8, wrap="word",
            insertbackground=PAL["white"],
        )
        self._trans_text.pack(fill=tk.BOTH, expand=True)
        self._trans_text.configure(state="disabled")

        # ── Transport controls ─────────────────────────────────────────────
        transport = tk.Frame(self, bg=PAL["card"], padx=14, pady=12)
        transport.pack(fill=tk.X, side=tk.BOTTOM)

        # Time labels
        time_row = tk.Frame(transport, bg=PAL["card"])
        time_row.pack(fill=tk.X)
        self._elapsed_var = tk.StringVar(value="0:00")
        self._total_var   = tk.StringVar(value="0:00")
        tk.Label(time_row, textvariable=self._elapsed_var,
                 font=FONT_BODY, fg=PAL["text"], bg=PAL["card"]).pack(side=tk.LEFT)
        tk.Label(time_row, textvariable=self._total_var,
                 font=FONT_BODY, fg=PAL["gray"], bg=PAL["card"]).pack(side=tk.RIGHT)

        # Scrubber
        self._scrub_var = tk.DoubleVar(value=0)
        self._scrubber  = ttk.Scale(
            transport, from_=0, to=100,
            orient="horizontal",
            variable=self._scrub_var,
            command=self._on_scrub,
        )
        style = ttk.Style()
        style.configure("Replay.Horizontal.TScale", background=PAL["card"])
        self._scrubber.configure(style="Replay.Horizontal.TScale")
        self._scrubber.pack(fill=tk.X, pady=6)
        self._scrubber.bind("<ButtonPress-1>",   lambda _: self._begin_scrub())
        self._scrubber.bind("<ButtonRelease-1>", lambda _: self._end_scrub())

        # Buttons
        btn_row = tk.Frame(transport, bg=PAL["card"])
        btn_row.pack()
        self._play_btn  = self._ctrl_btn(btn_row, "▶  Play",  self._play,  PAL["green"])
        self._pause_btn = self._ctrl_btn(btn_row, "⏸  Pause", self._pause, PAL["yellow"])
        self._stop_btn  = self._ctrl_btn(btn_row, "⏹  Stop",  self._stop,  PAL["orange"])
        self._pause_btn.configure(state="disabled")
        self._stop_btn.configure(state="disabled")

        # Session selector
        sel_row = tk.Frame(transport, bg=PAL["card"])
        sel_row.pack(fill=tk.X, pady=(8, 0))
        tk.Label(sel_row, text="Load session:",
                 font=FONT_SM, fg=PAL["gray"], bg=PAL["card"]).pack(side=tk.LEFT)
        self._session_var = tk.StringVar()
        self._session_combo = ttk.Combobox(
            sel_row, textvariable=self._session_var,
            width=50, state="readonly",
            font=FONT_SM
        )
        self._session_combo.pack(side=tk.LEFT, padx=8)
        self._session_combo.bind("<<ComboboxSelected>>", self._load_from_combo)
        self._ctrl_btn(sel_row, "Load", self._load_from_combo, PAL["accent"])

        self._populate_session_list()

    def _ctrl_btn(self, parent, text, cmd, color) -> tk.Button:
        btn = tk.Button(
            parent, text=text, command=cmd,
            bg=color, fg=PAL["bg"],
            font=("Helvetica", 10, "bold"),
            relief="flat", cursor="hand2",
            padx=14, pady=6,
        )
        btn.pack(side=tk.LEFT, padx=6)
        return btn

    # ─── Session loading ──────────────────────────────────────────────────────

    def _populate_session_list(self):
        """Fill the combo with all past interviews."""
        interviews = self.db.get_all_interviews()
        items = []
        self._interview_map = {}
        for iv in interviews:
            date = (iv.get("session_date") or "")[:16]
            name = iv.get("candidate_name", "Unknown")
            score = iv.get("overall_score") or 0
            label = f"{date}  |  {name}  |  Score: {score:.0f}"
            items.append(label)
            self._interview_map[label] = iv["id"]
        self._session_combo["values"] = items

    def load_interview(self, interview_id: int):
        """Load and prepare a specific interview for replay."""
        interview = self.db.get_interview(interview_id)
        scores    = self.db.get_scores(interview_id)
        report    = self.db.get_report(interview_id)

        if not interview or not scores:
            messagebox.showwarning("Not Found",
                                   "No data found for this session.")
            return

        metrics    = scores.get("raw_metrics", {}) or {}
        transcripts = report.get("improvements", []) if report else []
        # Pull transcripts from raw_metrics if available
        if "transcripts" in metrics:
            transcripts = metrics["transcripts"]

        duration = interview.get("duration_sec") or 60.0
        wav_path = interview.get("recording_path") or ""

        self._replay.load_session(
            scores       = scores,
            metrics      = metrics,
            transcripts  = transcripts,
            duration_sec = duration,
            wav_path     = wav_path,
        )
        self._duration = duration

        # Update scrubber range
        self._scrubber.configure(to=duration)
        self._total_var.set(self._fmt_time(duration))

        cand_name = ""
        from database_manager import DatabaseManager
        cand = self.db.get_candidate(interview.get("candidate_id", 0))
        if cand:
            cand_name = cand.get("name", "")
        date_str = (interview.get("session_date") or "")[:16]
        self._session_label.configure(
            text=f"{cand_name}  ·  {date_str}  ·  {duration:.0f}s"
        )

        # Reset display
        self._trans_text.configure(state="normal")
        self._trans_text.delete("1.0", tk.END)
        self._trans_text.configure(state="disabled")
        for g in self._gauges.values():
            g.set_value(0)

    def _load_from_combo(self, _event=None):
        label = self._session_var.get()
        iid   = self._interview_map.get(label)
        if iid:
            self.load_interview(iid)

    # ─── Transport ────────────────────────────────────────────────────────────

    def _play(self):
        if self._duration == 0:
            messagebox.showinfo("No Session", "Load a session first.")
            return
        self._replay.play(start_offset=self._replay.current_position)
        self._play_btn.configure(state="disabled")
        self._pause_btn.configure(state="normal")
        self._stop_btn.configure(state="normal")
        self._tick_ui()

    def _pause(self):
        self._replay.pause()
        self._play_btn.configure(state="normal")
        self._pause_btn.configure(state="disabled")

    def _stop(self):
        self._replay.stop()
        self._play_btn.configure(state="normal")
        self._pause_btn.configure(state="disabled")
        self._stop_btn.configure(state="disabled")
        self._scrub_var.set(0)
        self._elapsed_var.set("0:00")

    # ─── Scrubber ─────────────────────────────────────────────────────────────

    def _begin_scrub(self):
        self._scrub_drag = True
        if self._replay.is_playing:
            self._replay.pause()

    def _end_scrub(self):
        self._scrub_drag = False
        pos = self._scrub_var.get()
        self._replay.seek(pos)
        if not self._replay.is_playing:
            self._play()

    def _on_scrub(self, val):
        if self._scrub_drag:
            self._elapsed_var.set(self._fmt_time(float(val)))

    # ─── Callbacks from ReplayManager ─────────────────────────────────────────

    def _on_tick(self, elapsed: float, snapshot: Dict):
        """Called from replay thread — schedule GUI update on main thread."""
        self.after(0, lambda e=elapsed, s=snapshot: self._apply_tick(e, s))

    def _apply_tick(self, elapsed: float, snapshot: Dict):
        if not self._scrub_drag:
            self._scrub_var.set(elapsed)
            self._elapsed_var.set(self._fmt_time(elapsed))

        for key, gauge in self._gauges.items():
            gauge.set_value(snapshot.get(key, 0))

        for key, lbl in self._text_metrics.items():
            val = snapshot.get(key, 0)
            if isinstance(val, float):
                lbl.configure(text=f"{val:.1f}")
            else:
                lbl.configure(text=str(val))

    def _on_transcript(self, text: str):
        self.after(0, lambda t=text: self._append_transcript(t))

    def _append_transcript(self, text: str):
        self._trans_text.configure(state="normal")
        self._trans_text.insert(tk.END, text + " ")
        self._trans_text.see(tk.END)
        self._trans_text.configure(state="disabled")

    def _on_complete(self):
        self.after(0, self._handle_complete)

    def _handle_complete(self):
        self._play_btn.configure(state="normal")
        self._pause_btn.configure(state="disabled")
        self._stop_btn.configure(state="disabled")

    def _tick_ui(self):
        """Keep scrubber in sync during playback."""
        if self._replay.is_playing:
            pos = self._replay.current_position
            if not self._scrub_drag:
                self._scrub_var.set(pos)
                self._elapsed_var.set(self._fmt_time(pos))
            self.after(200, self._tick_ui)

    @staticmethod
    def _fmt_time(secs: float) -> str:
        s = int(secs)
        return f"{s // 60}:{s % 60:02d}"
