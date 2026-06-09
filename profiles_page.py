"""
profiles_page.py
----------------
Tkinter page for managing multiple candidate profiles.
Displays avatar cards, session stats, trend arrows, and
provides Create / Edit / Delete / Switch actions.
"""

import tkinter as tk
from tkinter import ttk, messagebox, simpledialog
from typing import Callable, Optional, List

from profile_manager import ProfileManager, CandidateProfile

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

FONT_H2    = ("Helvetica", 14, "bold")
FONT_H3    = ("Helvetica", 11, "bold")
FONT_BODY  = ("Helvetica", 10)
FONT_SMALL = ("Helvetica", 8)
FONT_INIT  = ("Helvetica", 20, "bold")


class ProfileCard(tk.Frame):
    """
    Single candidate profile card widget.
    Shows avatar initials, name, stats, and action buttons.
    """

    def __init__(
        self,
        parent,
        profile: CandidateProfile,
        on_select: Callable,
        on_delete: Callable,
        on_edit:   Callable,
        is_active: bool = False,
        **kw
    ):
        border_col = PAL["accent"] if is_active else PAL["border"]
        super().__init__(
            parent,
            bg=PAL["card"],
            highlightthickness=2,
            highlightbackground=border_col,
            padx=14, pady=14,
            **kw
        )
        self.profile = profile

        # ── Avatar circle (Canvas) ────────────────────────────────────────────
        avatar = tk.Canvas(self, width=64, height=64, bg=PAL["card"],
                           highlightthickness=0)
        avatar.pack()
        avatar.create_oval(2, 2, 62, 62, fill=profile.avatar_color, outline="")
        avatar.create_text(32, 32, text=profile.initials,
                           font=FONT_INIT, fill=PAL["bg"])

        # ── Name ──────────────────────────────────────────────────────────────
        name_lbl = tk.Label(self, text=profile.name,
                            font=FONT_H3, fg=PAL["white"], bg=PAL["card"])
        name_lbl.pack(pady=(6, 0))

        if profile.email:
            tk.Label(self, text=profile.email, font=FONT_SMALL,
                     fg=PAL["gray"], bg=PAL["card"]).pack()

        # ── Stats row ─────────────────────────────────────────────────────────
        stats = tk.Frame(self, bg=PAL["card"])
        stats.pack(fill=tk.X, pady=8)

        self._stat(stats, "Sessions",  str(profile.total_sessions), PAL["accent"])
        self._stat(stats, "Best",      f"{profile.best_score:.0f}",  PAL["green"])
        self._stat(stats, "Avg",       f"{profile.avg_score:.0f}",   PAL["yellow"])

        # Trend
        trend_frame = tk.Frame(self, bg=PAL["card"])
        trend_frame.pack()
        tk.Label(trend_frame, text="Trend ",
                 font=FONT_SMALL, fg=PAL["gray"], bg=PAL["card"]).pack(side=tk.LEFT)
        tk.Label(trend_frame,
                 text=f"{profile.trend_arrow} {abs(profile.improvement_pct):.0f}%",
                 font=("Helvetica", 10, "bold"),
                 fg=profile.trend_color, bg=PAL["card"]).pack(side=tk.LEFT)

        # ── Buttons ───────────────────────────────────────────────────────────
        btn_row = tk.Frame(self, bg=PAL["card"])
        btn_row.pack(fill=tk.X, pady=(10, 0))

        self._btn(btn_row, "Switch",  lambda: on_select(profile), PAL["accent"])
        self._btn(btn_row, "Edit",    lambda: on_edit(profile),   PAL["gray"])
        self._btn(btn_row, "Delete",  lambda: on_delete(profile), PAL["orange"])

        if is_active:
            tk.Label(self, text="● Active",
                     font=FONT_SMALL, fg=PAL["green"], bg=PAL["card"]).pack(pady=(4, 0))

    def _stat(self, parent, label: str, value: str, color: str):
        f = tk.Frame(parent, bg=PAL["card"])
        f.pack(side=tk.LEFT, expand=True)
        tk.Label(f, text=value, font=("Helvetica", 12, "bold"),
                 fg=color, bg=PAL["card"]).pack()
        tk.Label(f, text=label, font=FONT_SMALL,
                 fg=PAL["gray"], bg=PAL["card"]).pack()

    def _btn(self, parent, text: str, cmd: Callable, color: str):
        tk.Button(
            parent, text=text, command=cmd,
            bg=color, fg=PAL["bg"],
            font=("Helvetica", 8, "bold"),
            relief="flat", cursor="hand2",
            padx=8, pady=4,
        ).pack(side=tk.LEFT, padx=2, expand=True, fill=tk.X)


class ProfilesPage(tk.Frame):
    """
    Full-page profiles browser embedded in the main GUI.
    Call build() once, then refresh() to reload data.
    """

    def __init__(
        self,
        parent,
        profile_manager: ProfileManager,
        on_candidate_selected: Callable,   # callback(name: str, id: int)
        active_candidate_id: int = 0,
    ):
        super().__init__(parent, bg=PAL["bg"])
        self._pm          = profile_manager
        self._on_select   = on_candidate_selected
        self._active_id   = active_candidate_id
        self._card_frames: List[ProfileCard] = []
        self._build()

    # ─── Build ────────────────────────────────────────────────────────────────

    def _build(self):
        # Header
        header = tk.Frame(self, bg=PAL["bg"])
        header.pack(fill=tk.X, padx=20, pady=(14, 6))
        tk.Label(header, text="Candidate Profiles",
                 font=FONT_H2, fg=PAL["accent"], bg=PAL["bg"]).pack(side=tk.LEFT)

        btn_frame = tk.Frame(header, bg=PAL["bg"])
        btn_frame.pack(side=tk.RIGHT)
        self._btn(btn_frame, "＋ New Profile", self._create_profile, PAL["green"])
        self._btn(btn_frame, "⟳ Refresh",     self.refresh,          PAL["accent"])

        # Search bar
        search_frame = tk.Frame(self, bg=PAL["bg"])
        search_frame.pack(fill=tk.X, padx=20, pady=(0, 8))
        tk.Label(search_frame, text="Search:", font=FONT_BODY,
                 fg=PAL["gray"], bg=PAL["bg"]).pack(side=tk.LEFT)
        self._search_var = tk.StringVar()
        self._search_var.trace_add("write", lambda *_: self._filter_cards())
        tk.Entry(
            search_frame, textvariable=self._search_var,
            font=FONT_BODY, bg=PAL["border"], fg=PAL["white"],
            insertbackground=PAL["white"], relief="flat", width=28
        ).pack(side=tk.LEFT, padx=8)

        # Scrollable card grid
        container = tk.Frame(self, bg=PAL["bg"])
        container.pack(fill=tk.BOTH, expand=True, padx=16)

        self._canvas = tk.Canvas(container, bg=PAL["bg"], highlightthickness=0)
        scroll = ttk.Scrollbar(container, orient="vertical",
                               command=self._canvas.yview)
        self._canvas.configure(yscrollcommand=scroll.set)
        scroll.pack(side=tk.RIGHT, fill=tk.Y)
        self._canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        self._grid_frame = tk.Frame(self._canvas, bg=PAL["bg"])
        self._canvas_window = self._canvas.create_window(
            (0, 0), window=self._grid_frame, anchor="nw"
        )
        self._grid_frame.bind(
            "<Configure>",
            lambda e: self._canvas.configure(
                scrollregion=self._canvas.bbox("all")
            )
        )
        self._canvas.bind("<Configure>", self._on_canvas_resize)

        self.refresh()

    def refresh(self, active_id: int = None):
        """Reload all profiles from DB and re-render cards."""
        if active_id is not None:
            self._active_id = active_id

        # Clear existing cards
        for w in self._grid_frame.winfo_children():
            w.destroy()
        self._card_frames.clear()

        profiles = self._pm.get_all_profiles()
        if not profiles:
            tk.Label(
                self._grid_frame,
                text="No profiles yet.\nClick '＋ New Profile' to get started.",
                font=FONT_BODY, fg=PAL["gray"], bg=PAL["bg"], justify="center"
            ).pack(expand=True, pady=60)
            return

        query = self._search_var.get().lower()
        for profile in profiles:
            if query and query not in profile.name.lower():
                continue
            card = ProfileCard(
                self._grid_frame, profile,
                on_select=self._select_profile,
                on_delete=self._delete_profile,
                on_edit=self._edit_profile,
                is_active=(profile.id == self._active_id),
            )
            self._card_frames.append(card)

        self._layout_cards()

    # ─── Card layout (responsive grid) ───────────────────────────────────────

    def _layout_cards(self):
        for w in self._grid_frame.winfo_children():
            w.grid_forget()

        cols = max(1, (self._canvas.winfo_width() or 800) // 240)
        for i, card in enumerate(self._card_frames):
            card.grid(row=i // cols, column=i % cols,
                      padx=8, pady=8, sticky="nsew")

        for c in range(cols):
            self._grid_frame.columnconfigure(c, weight=1)

    def _on_canvas_resize(self, event):
        self._canvas.itemconfig(self._canvas_window, width=event.width)
        self._layout_cards()

    def _filter_cards(self):
        self.refresh()

    # ─── Actions ──────────────────────────────────────────────────────────────

    def _create_profile(self):
        name = simpledialog.askstring(
            "New Profile", "Enter candidate name:",
            parent=self
        )
        if not name or not name.strip():
            return
        email = simpledialog.askstring(
            "New Profile", "Enter email (optional):",
            parent=self
        ) or ""
        try:
            profile = self._pm.create_profile(name, email)
            self.refresh()
            messagebox.showinfo("Profile Created",
                                f"Profile '{profile.name}' created successfully.")
        except ValueError as e:
            messagebox.showerror("Error", str(e))

    def _select_profile(self, profile: CandidateProfile):
        self._active_id = profile.id
        self._on_select(profile.name, profile.id)
        self.refresh()

    def _edit_profile(self, profile: CandidateProfile):
        name = simpledialog.askstring(
            "Edit Profile", "New name:",
            initialvalue=profile.name, parent=self
        )
        if not name or not name.strip():
            return
        email = simpledialog.askstring(
            "Edit Profile", "New email:",
            initialvalue=profile.email or "", parent=self
        ) or ""
        self._pm.update_profile(profile.id, name=name, email=email)
        self.refresh()

    def _delete_profile(self, profile: CandidateProfile):
        if not messagebox.askyesno(
            "Delete Profile",
            f"Delete '{profile.name}' and ALL their interview data?\n"
            "This cannot be undone."
        ):
            return
        ok = self._pm.delete_profile(profile.id)
        if ok:
            if profile.id == self._active_id:
                self._active_id = 0
            self.refresh()
        else:
            messagebox.showerror("Error", "Could not delete profile.")

    # ─── Helper ───────────────────────────────────────────────────────────────

    def _btn(self, parent, text: str, cmd: Callable, color: str):
        tk.Button(
            parent, text=text, command=cmd,
            bg=color, fg=PAL["bg"],
            font=("Helvetica", 9, "bold"),
            relief="flat", cursor="hand2",
            padx=10, pady=6,
        ).pack(side=tk.LEFT, padx=4)
