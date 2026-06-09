"""
analytics_dashboard.py
-----------------------
Renders matplotlib charts embedded in the Tkinter GUI.
Shows progress trends, score distributions, and speech metrics.
"""

import tkinter as tk
from tkinter import ttk
from typing import List, Dict, Optional

try:
    import matplotlib
    matplotlib.use("TkAgg")
    import matplotlib.pyplot as plt
    import matplotlib.patches as mpatches
    from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
    from matplotlib.figure import Figure
    import numpy as np
    MPL_AVAILABLE = True
except ImportError:
    MPL_AVAILABLE = False

# Dark theme palette matching the GUI
DARK_BG     = "#0D1117"
CARD_BG     = "#161B22"
ACCENT      = "#00D4FF"
GREEN       = "#3FB950"
ORANGE      = "#F78166"
YELLOW      = "#E3B341"
GRAY        = "#8B949E"
TEXT        = "#C9D1D9"


class AnalyticsDashboard:
    """
    Embeds a multi-chart matplotlib figure into a given Tkinter frame.
    Charts update when refresh() is called with new history data.
    """

    def __init__(self, parent_frame: tk.Frame):
        self.parent = parent_frame
        self.canvas: Optional[FigureCanvasTkAgg] = None
        self.fig:    Optional[Figure] = None
        self._build_placeholder()

    # ─── Public API ───────────────────────────────────────────────────────────

    def refresh(self, history: List[Dict], candidate_name: str = ""):
        """Rebuild all charts with the provided history list."""
        if not MPL_AVAILABLE:
            self._show_no_mpl_message()
            return
        if not history:
            self._show_no_data_message()
            return

        # Clear previous figure
        if self.canvas:
            self.canvas.get_tk_widget().destroy()
        if self.fig:
            plt.close(self.fig)

        self.fig = Figure(figsize=(11, 7), facecolor=DARK_BG, tight_layout=True)
        self._apply_global_style()

        dates    = [h.get("session_date", f"#{i+1}")[:10] for i, h in enumerate(history)]
        overall  = [h.get("overall_score",       0) for h in history]
        eye      = [h.get("eye_contact_score",   0) for h in history]
        comm     = [h.get("communication_score", 0) for h in history]
        speech   = [h.get("speech_score",        0) for h in history]
        wpm      = [h.get("words_per_minute",     0) for h in history]
        fillers  = [h.get("filler_word_count",    0) for h in history]
        eye_pct  = [h.get("eye_contact_pct",      0) for h in history]

        # ── 2×3 grid of subplots ──────────────────────────────────────────────
        axs = self.fig.subplots(2, 3)

        self._plot_trend(axs[0][0], dates, overall,  "Overall Score",      ACCENT)
        self._plot_trend(axs[0][1], dates, eye,      "Eye Contact Score",  GREEN)
        self._plot_trend(axs[0][2], dates, speech,   "Speech Score",       YELLOW)
        self._plot_bar  (axs[1][0], dates, eye_pct,  "Eye Contact %",      ACCENT)
        self._plot_bar  (axs[1][1], dates, wpm,      "Words / Minute",     ORANGE)
        self._plot_bar  (axs[1][2], dates, fillers,  "Filler Words",       GRAY, invert=True)

        # Super-title
        title = f"Performance Analytics — {candidate_name}" if candidate_name else "Performance Analytics"
        self.fig.suptitle(title, color=TEXT, fontsize=12, fontweight="bold", y=1.01)

        self.canvas = FigureCanvasTkAgg(self.fig, master=self.parent)
        self.canvas.draw()
        self.canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)

    def refresh_radar(self, scores: Dict, frame: tk.Frame):
        """Draw a radar/spider chart for a single session's sub-scores."""
        if not MPL_AVAILABLE:
            return
        categories = ["Eye\nContact", "Speech", "Communication", "Confidence", "Overall"]
        vals = [
            scores.get("eye_contact_score",   0),
            scores.get("speech_score",        0),
            scores.get("communication_score", 0),
            scores.get("confidence_score",    0),
            scores.get("overall_score",       0),
        ]

        fig = Figure(figsize=(4, 4), facecolor=CARD_BG)
        self._apply_global_style()
        ax = fig.add_subplot(111, polar=True)
        ax.set_facecolor(CARD_BG)

        N = len(categories)
        angles = [n / float(N) * 2 * 3.14159 for n in range(N)]
        angles += angles[:1]
        vals_plot = vals + vals[:1]

        ax.plot(angles, vals_plot, color=ACCENT, linewidth=2)
        ax.fill(angles, vals_plot, color=ACCENT, alpha=0.2)
        ax.set_xticks(angles[:-1])
        ax.set_xticklabels(categories, color=TEXT, fontsize=8)
        ax.set_ylim(0, 100)
        ax.set_yticks([25, 50, 75, 100])
        ax.set_yticklabels(["25", "50", "75", "100"], color=GRAY, fontsize=7)
        ax.grid(color=GRAY, alpha=0.3)
        ax.spines["polar"].set_color(GRAY)
        ax.tick_params(colors=TEXT)

        canvas = FigureCanvasTkAgg(fig, master=frame)
        canvas.draw()
        canvas.get_tk_widget().pack(fill=tk.BOTH, expand=True)
        return canvas

    # ─── Chart helpers ────────────────────────────────────────────────────────

    def _plot_trend(self, ax, dates, values, title: str, color: str):
        """Line chart with markers and shaded area."""
        xs = list(range(len(dates)))
        ax.set_facecolor(CARD_BG)
        ax.plot(xs, values, color=color, linewidth=2, marker="o", markersize=5)
        ax.fill_between(xs, values, alpha=0.15, color=color)
        ax.set_title(title, color=TEXT, fontsize=9, pad=6)
        ax.set_xticks(xs)
        ax.set_xticklabels(
            [d[-5:] for d in dates], color=GRAY, fontsize=7,
            rotation=30, ha="right"
        )
        ax.set_ylim(0, 105)
        ax.tick_params(axis="y", colors=GRAY, labelsize=7)
        ax.spines[:].set_color(GRAY)
        ax.spines[:].set_alpha(0.3)
        ax.grid(axis="y", color=GRAY, alpha=0.15, linestyle="--")
        # Best / current labels
        if values:
            ax.annotate(
                f"Best: {max(values):.0f}",
                xy=(0.98, 0.95), xycoords="axes fraction",
                color=color, fontsize=7, ha="right"
            )

    def _plot_bar(self, ax, dates, values, title: str, color: str, invert: bool = False):
        """Vertical bar chart."""
        xs = list(range(len(dates)))
        ax.set_facecolor(CARD_BG)
        bars = ax.bar(xs, values, color=color, alpha=0.75, width=0.6)
        ax.set_title(title, color=TEXT, fontsize=9, pad=6)
        ax.set_xticks(xs)
        ax.set_xticklabels(
            [d[-5:] for d in dates], color=GRAY, fontsize=7,
            rotation=30, ha="right"
        )
        ax.tick_params(axis="y", colors=GRAY, labelsize=7)
        ax.spines[:].set_color(GRAY)
        ax.spines[:].set_alpha(0.3)
        ax.grid(axis="y", color=GRAY, alpha=0.15, linestyle="--")
        # Value labels on bars
        for bar, val in zip(bars, values):
            ax.text(
                bar.get_x() + bar.get_width() / 2,
                bar.get_height() + 0.5,
                f"{val:.0f}",
                ha="center", va="bottom", color=TEXT, fontsize=7
            )

    def _apply_global_style(self):
        plt.rcParams.update({
            "font.family":      "DejaVu Sans",
            "axes.facecolor":   CARD_BG,
            "figure.facecolor": DARK_BG,
            "text.color":       TEXT,
            "axes.labelcolor":  TEXT,
            "xtick.color":      GRAY,
            "ytick.color":      GRAY,
        })

    # ─── Placeholder / error states ───────────────────────────────────────────

    def _build_placeholder(self):
        lbl = tk.Label(
            self.parent,
            text="No interview data yet.\nComplete a session to see analytics.",
            font=("Helvetica", 12), fg=GRAY, bg=DARK_BG, justify="center"
        )
        lbl.pack(expand=True)

    def _show_no_data_message(self):
        for w in self.parent.winfo_children():
            w.destroy()
        lbl = tk.Label(
            self.parent,
            text="No sessions recorded yet.\nStart an interview to generate analytics.",
            font=("Helvetica", 12), fg=GRAY, bg=DARK_BG, justify="center"
        )
        lbl.pack(expand=True)

    def _show_no_mpl_message(self):
        for w in self.parent.winfo_children():
            w.destroy()
        lbl = tk.Label(
            self.parent,
            text="matplotlib not installed.\nRun: pip install matplotlib",
            font=("Helvetica", 12), fg=ORANGE, bg=DARK_BG, justify="center"
        )
        lbl.pack(expand=True)
