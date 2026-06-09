"""
notification_manager.py
------------------------
Lightweight in-app toast notification system for Tkinter.
Shows non-blocking slide-in banners for events like:
  - Eye contact lost
  - Filler word detected
  - Speaking too fast / slow
  - Session milestones
"""

import tkinter as tk
from typing import Optional
import threading
import time


PAL = {
    "bg":     "#0D1117",
    "card":   "#161B22",
    "accent": "#00D4FF",
    "green":  "#3FB950",
    "orange": "#F78166",
    "yellow": "#E3B341",
    "red":    "#FF4444",
    "text":   "#C9D1D9",
    "white":  "#FFFFFF",
}

# Map severity to colors
SEVERITY_COLORS = {
    "info":    PAL["accent"],
    "success": PAL["green"],
    "warning": PAL["yellow"],
    "error":   PAL["orange"],
    "tip":     "#7C3AED",
}


class Toast(tk.Toplevel):
    """
    A single toast notification window that auto-dismisses.
    Slides in from the bottom-right corner of the parent window.
    """

    def __init__(
        self,
        parent:     tk.Misc,
        message:    str,
        severity:   str = "info",
        duration_ms: int = 3500,
        icon:       str = "",
    ):
        super().__init__(parent)
        self.overrideredirect(True)       # borderless
        self.attributes("-topmost", True)
        self.attributes("-alpha", 0.0)    # start transparent

        color = SEVERITY_COLORS.get(severity, PAL["accent"])

        # Layout
        frame = tk.Frame(self, bg=PAL["card"],
                         highlightthickness=2,
                         highlightbackground=color)
        frame.pack(fill=tk.BOTH, expand=True)

        # Left accent bar
        tk.Frame(frame, bg=color, width=5).pack(side=tk.LEFT, fill=tk.Y)

        content = tk.Frame(frame, bg=PAL["card"], padx=12, pady=8)
        content.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # Icon + message
        if icon:
            tk.Label(content, text=icon, font=("Helvetica", 14),
                     fg=color, bg=PAL["card"]).pack(side=tk.LEFT, padx=(0, 8))

        tk.Label(
            content, text=message,
            font=("Helvetica", 9), fg=PAL["text"],
            bg=PAL["card"], wraplength=240, justify="left"
        ).pack(side=tk.LEFT)

        # Close button
        tk.Button(
            frame, text="✕", font=("Helvetica", 8),
            fg=PAL["text"], bg=PAL["card"],
            relief="flat", cursor="hand2",
            command=self._dismiss,
        ).pack(side=tk.RIGHT, anchor="n", padx=4, pady=4)

        self.update_idletasks()
        self._position(parent)
        self._fade_in()
        self.after(duration_ms, self._dismiss)

    # ─── Animation ────────────────────────────────────────────────────────────

    def _position(self, parent):
        """Place toast in bottom-right of parent window."""
        pw = parent.winfo_rootx() + parent.winfo_width()
        ph = parent.winfo_rooty() + parent.winfo_height()
        tw = self.winfo_width()  or 280
        th = self.winfo_height() or 60
        x  = pw - tw - 20
        y  = ph - th - 60
        self.geometry(f"+{x}+{y}")

    def _fade_in(self, alpha=0.0):
        if alpha <= 0.95:
            self.attributes("-alpha", alpha)
            self.after(20, lambda: self._fade_in(alpha + 0.08))
        else:
            self.attributes("-alpha", 1.0)

    def _dismiss(self):
        self._fade_out()

    def _fade_out(self, alpha=1.0):
        if alpha >= 0.05:
            self.attributes("-alpha", alpha)
            self.after(20, lambda: self._fade_out(alpha - 0.1))
        else:
            try:
                self.destroy()
            except tk.TclError:
                pass


class NotificationManager:
    """
    Manages a queue of toast notifications.
    Ensures only one toast is visible at a time (stacked with offset).
    Provides convenience methods for common interview events.
    """

    def __init__(self, root: tk.Tk):
        self._root  = root
        self._queue = []
        self._active_toasts = []

        # Cooldowns: prevent spamming the same notification
        self._last_sent: dict = {}
        self._cooldowns = {
            "eye_contact_lost": 8.0,
            "filler_detected":  5.0,
            "speed_warning":    10.0,
            "milestone":        60.0,
        }

    # ─── Public API ───────────────────────────────────────────────────────────

    def show(
        self,
        message:    str,
        severity:   str = "info",
        duration_ms: int = 3500,
        icon:       str = "",
        cooldown_key: Optional[str] = None,
    ):
        """Display a toast. Respects cooldown if cooldown_key is given."""
        if cooldown_key:
            last = self._last_sent.get(cooldown_key, 0)
            if time.time() - last < self._cooldowns.get(cooldown_key, 5.0):
                return
            self._last_sent[cooldown_key] = time.time()

        # Schedule on main thread
        self._root.after(0, lambda: self._create_toast(message, severity,
                                                        duration_ms, icon))

    # ─── Convenience shortcuts ────────────────────────────────────────────────

    def eye_contact_lost(self):
        self.show(
            "Maintain eye contact with the camera.",
            severity="warning", icon="👁",
            cooldown_key="eye_contact_lost",
        )

    def filler_detected(self, word: str):
        self.show(
            f"Filler word detected: '{word}'. Try a deliberate pause instead.",
            severity="warning", icon="🗣",
            cooldown_key="filler_detected",
        )

    def speaking_too_fast(self, wpm: float):
        self.show(
            f"You're speaking fast ({wpm:.0f} WPM). Slow down slightly.",
            severity="warning", icon="⚡",
            cooldown_key="speed_warning",
        )

    def speaking_too_slow(self, wpm: float):
        self.show(
            f"Speaking pace is slow ({wpm:.0f} WPM). Try to be more energetic.",
            severity="info", icon="🐢",
            cooldown_key="speed_warning",
        )

    def milestone(self, text: str):
        self.show(text, severity="success", icon="🎯",
                  cooldown_key="milestone", duration_ms=4000)

    def session_started(self, candidate: str):
        self.show(
            f"Session started for {candidate}. Good luck! 🚀",
            severity="success", icon="▶", duration_ms=4000,
        )

    def session_complete(self, score: float):
        if score >= 80:
            sev, icon = "success", "🏆"
        elif score >= 60:
            sev, icon = "info",    "📊"
        else:
            sev, icon = "warning", "📝"
        self.show(
            f"Session complete! Overall score: {score:.0f}/100",
            severity=sev, icon=icon, duration_ms=5000,
        )

    def report_generated(self, path: str):
        self.show(
            f"PDF report saved:\n{path}",
            severity="success", icon="📄", duration_ms=5000,
        )

    def tip(self, text: str):
        self.show(text, severity="tip", icon="💡", duration_ms=5000)

    # ─── Internal ─────────────────────────────────────────────────────────────

    def _create_toast(self, message, severity, duration_ms, icon):
        # Stack offset: each active toast shifts up
        offset = len(self._active_toasts) * 70
        toast  = Toast(self._root, message, severity, duration_ms, icon)
        # Reposition with stacking offset
        self._root.update_idletasks()
        pw = self._root.winfo_rootx() + self._root.winfo_width()
        ph = self._root.winfo_rooty() + self._root.winfo_height()
        tw = toast.winfo_width()  or 280
        th = toast.winfo_height() or 60
        x  = pw - tw - 20
        y  = ph - th - 60 - offset
        toast.geometry(f"+{x}+{y}")

        self._active_toasts.append(toast)
        toast.bind("<Destroy>", lambda _: self._on_toast_closed(toast))

    def _on_toast_closed(self, toast):
        if toast in self._active_toasts:
            self._active_toasts.remove(toast)
