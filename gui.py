"""
gui.py  (v2 — full integration)
--------------------------------
Complete Tkinter GUI for the AI Interview Analyzer.
Pages: Home · Interview · Analytics · Profiles · Replay · Reports · Settings

Integrates:
  - NotificationManager  (live toasts)
  - QuestionBank         (prompted questions with tips)
  - ProfilesPage         (multi-candidate management)
  - ReplayPage           (session playback with scrubber)
  - ExportManager        (CSV / JSON / Excel export)
"""

import tkinter as tk
from tkinter import ttk, messagebox, filedialog
import threading, time, os, subprocess, sys
from typing import Optional, Dict

try:
    from PIL import Image, ImageTk
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False

try:
    import cv2
    CV2_AVAILABLE = True
except ImportError:
    CV2_AVAILABLE = False

from settings_manager      import SettingsManager
from database_manager      import DatabaseManager
from interview_manager     import InterviewManager
from analytics_dashboard   import AnalyticsDashboard
from profile_manager       import ProfileManager
from profiles_page         import ProfilesPage
from replay_page           import ReplayPage
from question_bank         import QuestionBank
from notification_manager  import NotificationManager
from export_manager        import ExportManager

PAL = {
    "bg":     "#0D1117",
    "card":   "#161B22",
    "border": "#30363D",
    "accent": "#00D4FF",
    "accent2":"#7C3AED",
    "green":  "#3FB950",
    "orange": "#F78166",
    "yellow": "#E3B341",
    "text":   "#C9D1D9",
    "gray":   "#8B949E",
    "white":  "#FFFFFF",
    "red":    "#FF4444",
}
FONT_H2   = ("Helvetica", 14, "bold")
FONT_H3   = ("Helvetica", 11, "bold")
FONT_BODY = ("Helvetica", 10)
FONT_SM   = ("Helvetica",  8)
FONT_MONO = ("Courier",   10)


def card(parent, **kw):
    kw.setdefault("bg",                   PAL["card"])
    kw.setdefault("relief",               "flat")
    kw.setdefault("highlightthickness",   1)
    kw.setdefault("highlightbackground",  PAL["border"])
    return tk.Frame(parent, **kw)

def btn(parent, text, cmd, color=None, **kw):
    return tk.Button(
        parent, text=text, command=cmd,
        bg=color or PAL["accent"], fg=PAL["bg"],
        font=("Helvetica", 10, "bold"),
        relief="flat", cursor="hand2",
        padx=14, pady=7,
        activebackground=PAL["white"],
        activeforeground=PAL["bg"],
        **kw
    )

def lbl(parent, text, font=FONT_BODY, fg=None, **kw):
    return tk.Label(parent, text=text, font=font,
                    fg=fg or PAL["text"], bg=parent["bg"], **kw)


class ScoreGauge(tk.Canvas):
    def __init__(self, parent, size=110, label_text="Score", **kw):
        super().__init__(parent, width=size, height=size,
                         bg=parent["bg"], highlightthickness=0, **kw)
        self._size = size; self._label = label_text
        self._draw(0)

    def set_score(self, v):
        self._draw(max(0.0, min(100.0, float(v))))

    def _draw(self, v):
        self.delete("all")
        s, p = self._size, 12
        col = PAL["green"] if v >= 75 else PAL["yellow"] if v >= 50 else PAL["orange"]
        self.create_arc(p, p, s-p, s-p, start=0, extent=360,
                        outline=PAL["border"], width=8, style="arc")
        self.create_arc(p, p, s-p, s-p, start=135, extent=-(v/100*270),
                        outline=col, width=8, style="arc")
        self.create_text(s//2, s//2-8, text=f"{v:.0f}",
                         font=("Helvetica", int(s*0.18), "bold"), fill=PAL["white"])
        self.create_text(s//2, s//2+14, text=self._label,
                         font=("Helvetica", int(s*0.09)), fill=PAL["gray"])


class AIInterviewAnalyzerApp(tk.Tk):
    """Root application window."""

    def __init__(self):
        super().__init__()
        self.title("AI Interview Analyzer")
        self.geometry("1320x820")
        self.minsize(1100, 700)
        self.configure(bg=PAL["bg"])
        self.resizable(True, True)

        self.settings   = SettingsManager()
        self.db         = DatabaseManager()
        self.notif      = NotificationManager(self)
        self.qbank      = QuestionBank()
        self.prof_mgr   = ProfileManager(self.db)
        self.export_mgr = ExportManager(self.db, self.settings.reports_dir)
        self.manager: Optional[InterviewManager] = None

        self._cand_name = self.settings.get("default_candidate", "")
        self._cand_id: Optional[int] = None
        if self._cand_name:
            self._cand_id = self.db.get_or_create_candidate(self._cand_name)

        self._build_layout()
        self._show_page("home")
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    def _build_layout(self):
        self._sidebar = tk.Frame(self, bg=PAL["card"], width=210)
        self._sidebar.pack(side=tk.LEFT, fill=tk.Y)
        self._sidebar.pack_propagate(False)
        self._content = tk.Frame(self, bg=PAL["bg"])
        self._content.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self._build_sidebar()
        self._pages: Dict[str, tk.Frame] = {}
        self._cur_page = ""

    def _build_sidebar(self):
        f = tk.Frame(self._sidebar, bg=PAL["card"], pady=18)
        f.pack(fill=tk.X)
        tk.Label(f, text="🎯", font=("Helvetica", 30),
                 bg=PAL["card"], fg=PAL["accent"]).pack()
        tk.Label(f, text="AI Interview\nAnalyzer",
                 font=("Helvetica", 11, "bold"),
                 bg=PAL["card"], fg=PAL["white"], justify="center").pack()
        ttk.Separator(self._sidebar).pack(fill=tk.X, pady=6)

        nav = [
            ("🏠  Home",       "home"),
            ("🎬  Interview",   "interview"),
            ("📊  Analytics",   "analytics"),
            ("👤  Profiles",    "profiles"),
            ("⏮  Replay",       "replay"),
            ("📄  Reports",     "reports"),
            ("⚙️   Settings",    "settings"),
        ]
        self._nav_btns: Dict[str, tk.Button] = {}
        for text, pid in nav:
            b = tk.Button(
                self._sidebar, text=text,
                command=lambda p=pid: self._show_page(p),
                font=("Helvetica", 10), bg=PAL["card"],
                fg=PAL["text"], relief="flat", anchor="w",
                padx=20, pady=10, cursor="hand2",
                activebackground=PAL["border"],
                activeforeground=PAL["accent"],
            )
            b.pack(fill=tk.X)
            self._nav_btns[pid] = b

        ttk.Separator(self._sidebar).pack(fill=tk.X, pady=6, side=tk.BOTTOM)
        cf = tk.Frame(self._sidebar, bg=PAL["card"], pady=8)
        cf.pack(side=tk.BOTTOM, fill=tk.X)
        tk.Label(cf, text="Active Candidate", font=FONT_SM,
                 fg=PAL["gray"], bg=PAL["card"]).pack()
        self._cvar = tk.StringVar(value=self._cand_name or "Enter name →")
        tk.Entry(cf, textvariable=self._cvar,
                 font=FONT_BODY, bg=PAL["border"], fg=PAL["white"],
                 insertbackground=PAL["white"], relief="flat",
                 justify="center").pack(fill=tk.X, padx=10, pady=4)
        btn(cf, "Set", self._set_candidate, PAL["accent2"]).pack(
            fill=tk.X, padx=10, pady=(0, 4))

    def _show_page(self, pid):
        for k, b in self._nav_btns.items():
            active = (k == pid)
            b.configure(
                bg=PAL["accent"] if active else PAL["card"],
                fg=PAL["bg"]     if active else PAL["text"],
                font=("Helvetica", 10, "bold") if active else ("Helvetica", 10),
            )
        if pid not in self._pages:
            self._pages[pid] = self._make_page(pid)
        if self._cur_page and self._cur_page in self._pages:
            self._pages[self._cur_page].pack_forget()
        self._pages[pid].pack(fill=tk.BOTH, expand=True)
        self._cur_page = pid
        {"home": self._refresh_home,
         "analytics": self._refresh_analytics,
         "reports": self._refresh_reports,
         "profiles": self._refresh_profiles}.get(pid, lambda: None)()

    def _make_page(self, pid):
        frame = tk.Frame(self._content, bg=PAL["bg"])
        getattr(self, f"_build_{pid}")(frame)
        return frame

    # ── HOME ──────────────────────────────────────────────────────────────────

    def _build_home(self, f):
        hero = tk.Frame(f, bg=PAL["card"], pady=36)
        hero.pack(fill=tk.X, padx=20, pady=20)
        tk.Label(hero, text="🎯  AI Interview Analyzer",
                 font=("Helvetica", 26, "bold"),
                 fg=PAL["accent"], bg=PAL["card"]).pack()
        tk.Label(hero, text="Real-time AI coaching · Eye contact · Speech · PDF reports",
                 font=FONT_H3, fg=PAL["gray"], bg=PAL["card"]).pack(pady=4)
        bf = tk.Frame(hero, bg=PAL["card"]); bf.pack(pady=12)
        btn(bf, "▶  Start Interview",  lambda: self._show_page("interview"), PAL["green"]).pack(side=tk.LEFT, padx=6)
        btn(bf, "👤  Profiles",        lambda: self._show_page("profiles"),  PAL["accent2"]).pack(side=tk.LEFT, padx=6)
        btn(bf, "⏮  Replay",           lambda: self._show_page("replay"),    PAL["yellow"]).pack(side=tk.LEFT, padx=6)

        self._home_stats = tk.Frame(f, bg=PAL["bg"])
        self._home_stats.pack(fill=tk.X, padx=20, pady=4)

        feats = [
            ("👁","Eye Contact","Iris tracking · blink · gaze"),
            ("🗣","Speech","WPM · pauses · fillers"),
            ("😊","Expressions","Smile · stability · confidence"),
            ("📈","Analytics","Trend charts · progress"),
            ("⏮","Replay","Audio + animated metrics"),
            ("📄","PDF Reports","Strengths & improvements"),
        ]
        fr = tk.Frame(f, bg=PAL["bg"]); fr.pack(fill=tk.X, padx=20, pady=10)
        for icon, title, desc in feats:
            c = card(fr, padx=12, pady=12)
            c.pack(side=tk.LEFT, expand=True, fill=tk.BOTH, padx=5)
            tk.Label(c, text=f"{icon}  {title}", font=FONT_H3,
                     fg=PAL["accent"], bg=PAL["card"]).pack(anchor="w")
            tk.Label(c, text=desc, font=FONT_SM, fg=PAL["gray"],
                     bg=PAL["card"], justify="left").pack(anchor="w", pady=3)

    def _refresh_home(self):
        for w in self._home_stats.winfo_children(): w.destroy()
        if not self._cand_id:
            lbl(self._home_stats, "Set a candidate in the sidebar to begin.",
                fg=PAL["gray"]).pack(pady=8)
            return
        s = self.db.get_dashboard_stats(self._cand_id)
        for title, val, col in [
            ("Sessions",  str(int(s.get("total_interviews") or 0)), PAL["accent"]),
            ("Best",      f"{s.get('best_score') or 0:.0f}",        PAL["green"]),
            ("Avg Score", f"{s.get('avg_overall') or 0:.0f}",       PAL["yellow"]),
            ("Avg Eye %", f"{s.get('avg_eye_contact') or 0:.0f}%",  PAL["accent"]),
            ("Avg WPM",   f"{s.get('avg_wpm') or 0:.0f}",           PAL["orange"]),
        ]:
            c = card(self._home_stats, padx=18, pady=14)
            c.pack(side=tk.LEFT, expand=True, fill=tk.BOTH, padx=5)
            tk.Label(c, text=val, font=("Helvetica", 22, "bold"),
                     fg=col, bg=PAL["card"]).pack()
            tk.Label(c, text=title, font=FONT_SM, fg=PAL["gray"],
                     bg=PAL["card"]).pack()

    # ── INTERVIEW ─────────────────────────────────────────────────────────────

    def _build_interview(self, f):
        ctrl = tk.Frame(f, bg=PAL["card"], pady=10, padx=14)
        ctrl.pack(fill=tk.X)
        tk.Label(ctrl, text="Interview Session",
                 font=FONT_H2, fg=PAL["accent"], bg=PAL["card"]).pack(side=tk.LEFT)
        self._timer_var = tk.StringVar(value="00:00")
        tk.Label(ctrl, textvariable=self._timer_var,
                 font=("Helvetica", 20, "bold"), fg=PAL["white"],
                 bg=PAL["card"]).pack(side=tk.LEFT, padx=26)
        self._stop_btn  = btn(ctrl, "⏹  Stop",  self._stop_interview, PAL["orange"])
        self._stop_btn.pack(side=tk.RIGHT, padx=5)
        self._start_btn = btn(ctrl, "▶  Start", self._start_interview, PAL["green"])
        self._start_btn.pack(side=tk.RIGHT, padx=5)

        body = tk.Frame(f, bg=PAL["bg"])
        body.pack(fill=tk.BOTH, expand=True, padx=14, pady=8)

        cam_card = card(body, padx=3, pady=3)
        cam_card.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        self._cam_lbl = tk.Label(cam_card, bg=PAL["card"],
                                  text="Camera feed appears here.",
                                  fg=PAL["gray"], font=FONT_BODY)
        self._cam_lbl.pack(fill=tk.BOTH, expand=True)

        right = tk.Frame(body, bg=PAL["bg"], width=290)
        right.pack(side=tk.RIGHT, fill=tk.Y, padx=(10, 0))
        right.pack_propagate(False)
        self._build_metrics_panel(right)

        # Question prompt card
        qf = card(f, padx=12, pady=10)
        qf.pack(fill=tk.X, padx=14, pady=(0, 6))
        qhdr = tk.Frame(qf, bg=PAL["card"]); qhdr.pack(fill=tk.X)
        tk.Label(qhdr, text="Interview Question",
                 font=FONT_H3, fg=PAL["accent"], bg=PAL["card"]).pack(side=tk.LEFT)
        self._q_cat_var  = tk.StringVar(value="All")
        self._q_diff_var = tk.StringVar(value="All")
        for var, vals, w in [
            (self._q_cat_var,  ["All"] + self.qbank.get_categories(), 14),
            (self._q_diff_var, ["All", "Easy", "Medium", "Hard"],     10),
        ]:
            ttk.Combobox(qhdr, textvariable=var, values=vals,
                         width=w, state="readonly",
                         font=FONT_SM).pack(side=tk.RIGHT, padx=4)
        btn(qhdr, "Next →", self._next_question, PAL["accent2"]).pack(side=tk.RIGHT, padx=4)

        self._q_text_var = tk.StringVar(value="Press 'Next →' for your first question.")
        tk.Label(qf, textvariable=self._q_text_var,
                 font=("Helvetica", 11, "bold"), fg=PAL["white"],
                 bg=PAL["card"], wraplength=700, justify="left").pack(anchor="w", pady=(6, 2))
        self._q_tip_var = tk.StringVar(value="")
        tk.Label(qf, textvariable=self._q_tip_var,
                 font=FONT_SM, fg=PAL["yellow"],
                 bg=PAL["card"], wraplength=700, justify="left").pack(anchor="w")

        tf = card(f, padx=10, pady=8)
        tf.pack(fill=tk.X, padx=14, pady=(0, 10))
        tk.Label(tf, text="Live Transcript", font=FONT_H3,
                 fg=PAL["accent"], bg=PAL["card"]).pack(anchor="w")
        self._trans_text = tk.Text(tf, height=4, bg=PAL["bg"], fg=PAL["text"],
                                    font=FONT_MONO, relief="flat",
                                    insertbackground=PAL["white"], wrap="word")
        self._trans_text.pack(fill=tk.X)
        self._trans_text.configure(state="disabled")

    def _build_metrics_panel(self, parent):
        self._status_var = tk.StringVar(value="● Not recording")
        tk.Label(parent, textvariable=self._status_var,
                 font=FONT_BODY, fg=PAL["gray"], bg=PAL["bg"]).pack(pady=(0, 6))
        gf = tk.Frame(parent, bg=PAL["bg"]); gf.pack()
        self._gauges: Dict[str, ScoreGauge] = {}
        for i, (key, label) in enumerate([
            ("confidence_score",  "Confidence"),
            ("eye_contact_score", "Eye Contact"),
            ("speech_score",      "Speech"),
            ("overall_score",     "Overall"),
        ]):
            g = ScoreGauge(gf, size=112, label_text=label)
            g.grid(row=i//2, column=i%2, padx=4, pady=4)
            self._gauges[key] = g

        mc = card(parent, padx=10, pady=8); mc.pack(fill=tk.X, pady=8)
        self._mlbls: Dict[str, tk.Label] = {}
        for key, disp in [
            ("wpm","WPM"), ("blinks","Blinks"),
            ("pause_count","Pauses"), ("filler_total","Fillers"),
            ("eye_contact","Eye Contact"), ("head_stable","Head Stable"),
        ]:
            row = tk.Frame(mc, bg=PAL["card"]); row.pack(fill=tk.X, pady=2)
            tk.Label(row, text=disp, font=FONT_SM, fg=PAL["gray"],
                     bg=PAL["card"], width=12, anchor="w").pack(side=tk.LEFT)
            l = tk.Label(row, text="—", font=("Helvetica", 10, "bold"),
                         fg=PAL["accent"], bg=PAL["card"])
            l.pack(side=tk.RIGHT)
            self._mlbls[key] = l

        tk.Label(parent, text="Mic Level", font=FONT_SM,
                 fg=PAL["gray"], bg=PAL["bg"]).pack()
        self._vol_cv = tk.Canvas(parent, height=14, bg=PAL["bg"],
                                  highlightthickness=0)
        self._vol_cv.pack(fill=tk.X, padx=4, pady=2)

    def _start_interview(self):
        name = self._cvar.get().strip()
        if not name or name == "Enter name →":
            messagebox.showwarning("Name Required", "Enter a candidate name first.")
            return
        self._cand_name = name
        self._cand_id   = self.db.get_or_create_candidate(name)
        self.manager = InterviewManager(
            settings=self.settings, db=self.db,
            on_metrics=self._on_live_metrics,
            on_transcript=self._on_transcript,
        )
        try:
            session = self.manager.start_session(name)
        except Exception as e:
            messagebox.showerror("Error", f"Could not start:\n{e}"); return

        self._start_btn.configure(state="disabled")
        self._stop_btn.configure(state="normal")
        self._status_var.set("● Recording…")
        self._cam_lbl.configure(text="")
        self.qbank.reset_session()
        self._next_question()
        self.notif.session_started(name)
        self._update_webcam()
        self._update_timer(session.start_time)
        self.after(60000, lambda: self.notif.milestone("1 minute in — great work!"))

    def _stop_interview(self):
        if not self.manager or not self.manager.is_running(): return
        self._start_btn.configure(state="normal")
        self._stop_btn.configure(state="disabled")
        self._status_var.set("● Processing…")
        def _finish():
            session     = self.manager.stop_session()
            report_path = self.manager.generate_report()
            self.after(0, lambda: self._show_results(session, report_path))
        threading.Thread(target=_finish, daemon=True).start()

    def _show_results(self, session, report_path):
        self._status_var.set("● Complete")
        sc = session.scores
        for k, g in self._gauges.items():
            g.set_score(sc.get(k, 0))
        self.notif.session_complete(sc.get("overall_score", 0))
        if report_path: self.notif.report_generated(report_path)
        messagebox.showinfo("Complete",
            f"Overall : {sc.get('overall_score',0):.0f}/100\n"
            f"Confidence: {sc.get('confidence_score',0):.0f}\n"
            f"Eye Contact: {sc.get('eye_contact_score',0):.0f}\n"
            f"Speech: {sc.get('speech_score',0):.0f}\n\n"
            f"Report → {report_path}")

    def _update_webcam(self):
        if not self.manager: return
        self.manager.update_frame()
        if CV2_AVAILABLE and PIL_AVAILABLE:
            frame = self.manager.get_current_frame()
            if frame is not None:
                h = self._cam_lbl.winfo_height() or 420
                w = self._cam_lbl.winfo_width()  or 580
                rgb   = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                img   = Image.fromarray(rgb).resize((w, h), Image.LANCZOS)
                photo = ImageTk.PhotoImage(img)
                self._cam_lbl.configure(image=photo)
                self._cam_lbl._photo = photo
        if self.manager.is_running():
            self.after(33, self._update_webcam)

    def _update_timer(self, t0):
        if self.manager and self.manager.is_running():
            e = int(time.time() - t0)
            self._timer_var.set(f"{e//60:02d}:{e%60:02d}")
            self.after(1000, lambda: self._update_timer(t0))

    def _on_live_metrics(self, m):
        self.after(0, lambda: self._apply_metrics(m))

    def _apply_metrics(self, m):
        self._mlbls["wpm"].configure(text=f"{m.get('wpm',0):.0f}")
        self._mlbls["blinks"].configure(text=str(m.get("blinks", 0)))
        self._mlbls["pause_count"].configure(text=str(m.get("pause_count", 0)))
        self._mlbls["filler_total"].configure(
            text=str(m.get("filler_counts", {}).get("total", 0)))
        ec = m.get("eye_contact", False)
        self._mlbls["eye_contact"].configure(
            text="Yes ✓" if ec else "No",
            fg=PAL["green"] if ec else PAL["orange"])
        hs = m.get("head_stable", True)
        self._mlbls["head_stable"].configure(
            text="Yes" if hs else "Moving",
            fg=PAL["green"] if hs else PAL["yellow"])
        rms  = min(m.get("rms_volume", 0), 8000)
        barw = int((rms / 8000) * (self._vol_cv.winfo_width() or 250))
        self._vol_cv.delete("all")
        self._vol_cv.create_rectangle(
            0, 0, barw, 14,
            fill=PAL["green"] if rms > 500 else PAL["gray"], outline="")
        wpm = m.get("wpm", 0)
        if wpm > 180:   self.notif.speaking_too_fast(wpm)
        elif 0 < wpm < 90: self.notif.speaking_too_slow(wpm)
        if not ec:      self.notif.eye_contact_lost()

    def _on_transcript(self, text):
        self.after(0, lambda t=text: self._append_trans(t))

    def _append_trans(self, text):
        self._trans_text.configure(state="normal")
        self._trans_text.insert(tk.END, text + " ")
        self._trans_text.see(tk.END)
        self._trans_text.configure(state="disabled")

    def _next_question(self):
        cat  = getattr(self, "_q_cat_var",  tk.StringVar(value="All")).get()
        diff = getattr(self, "_q_diff_var", tk.StringVar(value="All")).get()
        q = self.qbank.get_random(
            category   = None if cat  == "All" else cat,
            difficulty = None if diff == "All" else diff,
        )
        if q:
            self._q_text_var.set(q["question"])
            self._q_tip_var.set(f"💡 Tip: {q['tip']}")
        else:
            self._q_text_var.set("All questions shown — resetting…")
            self._q_tip_var.set("")
            self.qbank.reset_session()

    # ── ANALYTICS ─────────────────────────────────────────────────────────────

    def _build_analytics(self, f):
        tk.Label(f, text="Performance Analytics",
                 font=FONT_H2, fg=PAL["accent"], bg=PAL["bg"]).pack(
            anchor="w", padx=20, pady=(14, 4))
        self._analytics_frame = tk.Frame(f, bg=PAL["bg"])
        self._analytics_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=8)
        self._analytics_db = AnalyticsDashboard(self._analytics_frame)

    def _refresh_analytics(self):
        if not self._cand_id: return
        history = self.db.get_score_history(self._cand_id)
        for w in self._analytics_frame.winfo_children(): w.destroy()
        self._analytics_db = AnalyticsDashboard(self._analytics_frame)
        self._analytics_db.refresh(history, self._cand_name)

    # ── PROFILES ──────────────────────────────────────────────────────────────

    def _build_profiles(self, f):
        self._profiles_page = ProfilesPage(
            f, self.prof_mgr,
            on_candidate_selected=self._on_profile_selected,
            active_candidate_id=self._cand_id or 0,
        )
        self._profiles_page.pack(fill=tk.BOTH, expand=True)

    def _refresh_profiles(self):
        if hasattr(self, "_profiles_page"):
            self._profiles_page.refresh(active_id=self._cand_id or 0)

    def _on_profile_selected(self, name, cid):
        self._cand_name = name
        self._cand_id   = cid
        self._cvar.set(name)
        self.settings.set("default_candidate", name)
        self.notif.show(f"Switched to {name}", severity="success", icon="👤")

    # ── REPLAY ────────────────────────────────────────────────────────────────

    def _build_replay(self, f):
        self._replay_page = ReplayPage(f, self.db)
        self._replay_page.pack(fill=tk.BOTH, expand=True)

    # ── REPORTS ───────────────────────────────────────────────────────────────

    def _build_reports(self, f):
        hdr = tk.Frame(f, bg=PAL["bg"]); hdr.pack(fill=tk.X, padx=20, pady=(14, 4))
        tk.Label(hdr, text="Interview Reports",
                 font=FONT_H2, fg=PAL["accent"], bg=PAL["bg"]).pack(side=tk.LEFT)
        ebf = tk.Frame(hdr, bg=PAL["bg"]); ebf.pack(side=tk.RIGHT)
        btn(ebf, "⟳ Refresh",     self._refresh_reports,            PAL["accent2"]).pack(side=tk.LEFT, padx=3)
        btn(ebf, "📊 Export CSV",  lambda: self._export("csv"),      PAL["yellow"]).pack(side=tk.LEFT, padx=3)
        btn(ebf, "📋 Export JSON", lambda: self._export("json"),     PAL["gray"]).pack(side=tk.LEFT, padx=3)

        cols = ("date","candidate","overall","eye","speech","comm","file")
        tf   = card(f, padx=4, pady=4)
        tf.pack(fill=tk.BOTH, expand=True, padx=20, pady=8)
        style = ttk.Style(); style.theme_use("clam")
        style.configure("R.Treeview", background=PAL["card"], foreground=PAL["text"],
                        fieldbackground=PAL["card"], rowheight=28, font=("Helvetica", 9))
        style.configure("R.Treeview.Heading", background=PAL["border"],
                        foreground=PAL["accent"], font=("Helvetica", 9, "bold"))
        style.map("R.Treeview",
                  background=[("selected", PAL["accent2"])],
                  foreground=[("selected", PAL["white"])])
        self._tree = ttk.Treeview(tf, columns=cols, show="headings", style="R.Treeview")
        for col, head, w in [
            ("date","Date",140), ("candidate","Candidate",130),
            ("overall","Overall",72), ("eye","Eye",68),
            ("speech","Speech",68), ("comm","Comm",68), ("file","File",220),
        ]:
            self._tree.heading(col, text=head)
            self._tree.column(col, width=w, anchor="center")
        self._tree.column("candidate", anchor="w")
        self._tree.column("file",      anchor="w")
        sb2 = ttk.Scrollbar(tf, orient="vertical", command=self._tree.yview)
        self._tree.configure(yscrollcommand=sb2.set)
        self._tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        sb2.pack(side=tk.RIGHT, fill=tk.Y)
        self._tree.bind("<Double-1>", self._open_report)
        btn(f, "📂  Open Selected", self._open_report, PAL["accent"]).pack(pady=6)

    def _refresh_reports(self):
        if "reports" not in self._pages: return
        for row in self._tree.get_children(): self._tree.delete(row)
        for r in self.db.get_all_reports():
            iid = r.get("interview_id")
            sc  = (self.db.get_scores(iid) or {}) if iid else {}
            self._tree.insert("", tk.END, values=(
                (r.get("generated_at") or "")[:16],
                r.get("candidate_name", "—"),
                f"{sc.get('overall_score') or 0:.0f}",
                f"{sc.get('eye_contact_score') or 0:.0f}",
                f"{sc.get('speech_score') or 0:.0f}",
                f"{sc.get('communication_score') or 0:.0f}",
                os.path.basename(r.get("report_path", "")),
            ), tags=(r.get("report_path", ""),))

    def _open_report(self, _=None):
        sel = self._tree.selection()
        if not sel: return
        path = self._tree.item(sel[0], "tags")[0]
        if os.path.exists(path):
            if sys.platform == "win32":   os.startfile(path)
            elif sys.platform == "darwin": subprocess.call(["open", path])
            else:                          subprocess.call(["xdg-open", path])
        else:
            messagebox.showwarning("Not Found", f"File not found:\n{path}")

    def _export(self, fmt):
        if not self._cand_id:
            messagebox.showwarning("No Candidate", "Select a candidate first.")
            return
        path = (self.export_mgr.export_candidate_csv(self._cand_id) if fmt == "csv"
                else self.export_mgr.export_candidate_json(self._cand_id))
        messagebox.showinfo("Export Complete", f"Saved to:\n{path}")

    # ── SETTINGS ──────────────────────────────────────────────────────────────

    def _build_settings(self, f):
        tk.Label(f, text="Settings", font=FONT_H2,
                 fg=PAL["accent"], bg=PAL["bg"]).pack(anchor="w", padx=20, pady=(14, 4))
        cv = tk.Canvas(f, bg=PAL["bg"], highlightthickness=0)
        sb = ttk.Scrollbar(f, orient="vertical", command=cv.yview)
        cv.configure(yscrollcommand=sb.set)
        sb.pack(side=tk.RIGHT, fill=tk.Y)
        cv.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        inner = tk.Frame(cv, bg=PAL["bg"])
        cw    = cv.create_window((0, 0), window=inner, anchor="nw")
        inner.bind("<Configure>",
                   lambda e: cv.configure(scrollregion=cv.bbox("all")))
        cv.bind("<Configure>", lambda e: cv.itemconfig(cw, width=e.width))

        self._svars: Dict[str, tk.StringVar] = {}
        groups = [
            ("📷 Camera",   [("camera_index","Camera Index","int"),
                              ("frame_width","Frame Width","int"),
                              ("frame_height","Frame Height","int")]),
            ("🎙 Audio",    [("audio_sample_rate","Sample Rate (Hz)","int"),
                              ("silence_threshold","Silence Threshold","int"),
                              ("silence_duration_sec","Silence Duration (s)","float")]),
            ("📊 Analysis", [("ideal_wpm_min","WPM Min","int"),
                              ("ideal_wpm_max","WPM Max","int"),
                              ("eye_contact_threshold","Eye Contact Threshold","float"),
                              ("head_movement_threshold","Head Movement Px","int")]),
            ("⚖️  Weights",  [("weight_eye_contact","Eye Contact","float"),
                              ("weight_speech_speed","Speech Speed","float"),
                              ("weight_filler_words","Filler Words","float"),
                              ("weight_facial_stability","Facial Stability","float"),
                              ("weight_speaking_consistency","Consistency","float")]),
        ]
        for gtitle, items in groups:
            gf = card(inner, padx=16, pady=12)
            gf.pack(fill=tk.X, padx=20, pady=6)
            tk.Label(gf, text=gtitle, font=FONT_H3, fg=PAL["accent"],
                     bg=PAL["card"]).pack(anchor="w", pady=(0, 6))
            for key, disp, _ in items:
                row = tk.Frame(gf, bg=PAL["card"]); row.pack(fill=tk.X, pady=2)
                tk.Label(row, text=disp, font=FONT_BODY, fg=PAL["text"],
                         bg=PAL["card"], width=34, anchor="w").pack(side=tk.LEFT)
                v = tk.StringVar(value=str(self.settings.get(key, "")))
                self._svars[key] = v
                tk.Entry(row, textvariable=v, font=FONT_BODY,
                         bg=PAL["border"], fg=PAL["white"],
                         insertbackground=PAL["white"],
                         relief="flat", width=14).pack(side=tk.RIGHT)

        bf = tk.Frame(inner, bg=PAL["bg"]); bf.pack(fill=tk.X, padx=20, pady=12)
        btn(bf, "💾 Save",          self._save_settings).pack(side=tk.LEFT, padx=5)
        btn(bf, "↩ Reset Defaults", self._reset_settings, PAL["gray"]).pack(side=tk.LEFT)

    def _save_settings(self):
        for key, var in self._svars.items():
            try:
                cur = self.settings.get(key)
                self.settings.set(key, int(var.get()) if isinstance(cur, int)
                                  else float(var.get()) if isinstance(cur, float)
                                  else var.get())
            except ValueError: pass
        self.notif.show("Settings saved.", severity="success", icon="💾")

    def _reset_settings(self):
        if messagebox.askyesno("Reset", "Reset all settings to defaults?"):
            self.settings.reset_to_defaults()
            self.notif.show("Settings reset.", severity="info", icon="↩")

    def _set_candidate(self):
        name = self._cvar.get().strip()
        if not name or name == "Enter name →":
            messagebox.showwarning("Name Required", "Enter a candidate name.")
            return
        self._cand_name = name
        self._cand_id   = self.db.get_or_create_candidate(name)
        self.settings.set("default_candidate", name)
        self.notif.show(f"Active: {name}", severity="success", icon="👤")

    def _on_close(self):
        if self.manager and self.manager.is_running():
            if messagebox.askyesno("Quit", "Interview in progress. Stop and quit?"):
                self.manager.stop_session()
            else:
                return
        self.db.close()
        self.destroy()
