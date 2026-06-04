"""Shared visual theme for siteval's Tkinter UIs.

A clean, professional dark-green palette: white backgrounds with deep
forest-green chrome and accents. Imagery comes from Esri Wayback
(https://livingatlas.arcgis.com/wayback/). Centralising colours and fonts
here keeps the app, parameter UI, and validator visually consistent.
"""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk

# ── Palette (dark green) ─────────────────────────────────────────────────
BG = "#ffffff"            # primary background (white)
SURFACE = "#f3f7f3"       # subtle panel / card background (pale green-grey)
SURFACE_ALT = "#e7efe7"   # alternate panel shade
BORDER = "#cdddcd"        # hairline borders

GREEN = "#143d2b"         # primary brand — deep forest green (header, badges)
GREEN_DARK = "#0c2a1d"    # pressed / emphasis (darkest)
GREEN_MID = "#1f5c40"     # filled buttons, active state
GREEN_LIGHT = "#e4efe7"   # tinted highlight background
GREEN_TINT = "#bcd6c4"    # selected chips / scrollbar thumbs

TEXT = "#13261c"          # primary text (near-black green)
TEXT_MUTED = "#5d6f63"    # secondary text
TEXT_FAINT = "#93a597"    # hints / placeholders
ON_GREEN = "#ffffff"      # text on green fills

# Decision colours (validator) — semantic green / red / yellow.
ACCEPT = "#2e7d32"        # green
REJECT = "#c62828"        # red
CAUTION = "#f9a825"       # yellow

# ── Fonts ────────────────────────────────────────────────────────────────
FONT_FAMILY = "Segoe UI"          # clean default on Windows; falls back gracefully
FONT_MONO = "Consolas"

H1 = (FONT_FAMILY, 22, "bold")
H2 = (FONT_FAMILY, 15, "bold")
H3 = (FONT_FAMILY, 12, "bold")
BODY = (FONT_FAMILY, 11)
BODY_BOLD = (FONT_FAMILY, 11, "bold")
SMALL = (FONT_FAMILY, 9)
SMALL_BOLD = (FONT_FAMILY, 9, "bold")
MONO = (FONT_MONO, 9)


def apply_ttk_theme(root: tk.Misc) -> ttk.Style:
    """Configure ttk widgets (Progressbar, Separator, Scrollbar) to match."""
    style = ttk.Style(root)
    try:
        style.theme_use("clam")
    except tk.TclError:
        pass

    style.configure(
        "Siteval.Horizontal.TProgressbar",
        troughcolor=SURFACE_ALT,
        background=GREEN_MID,
        bordercolor=BORDER,
        lightcolor=GREEN_MID,
        darkcolor=GREEN_MID,
        thickness=14,
    )
    style.configure(
        "Siteval.TSeparator",
        background=BORDER,
    )
    style.configure(
        "Siteval.Vertical.TScrollbar",
        background=GREEN_TINT,
        troughcolor=SURFACE,
        bordercolor=BORDER,
        arrowcolor=GREEN_DARK,
    )
    style.configure(
        "Siteval.Horizontal.TScrollbar",
        background=GREEN_TINT,
        troughcolor=SURFACE,
        bordercolor=BORDER,
        arrowcolor=GREEN_DARK,
    )
    return style


# ── Reusable widget factories ────────────────────────────────────────────

def primary_button(parent, text: str, command, **kwargs) -> tk.Button:
    """A filled green call-to-action button with hover feedback."""
    btn = tk.Button(
        parent, text=text, command=command,
        bg=GREEN_MID, fg=ON_GREEN,
        activebackground=GREEN_DARK, activeforeground=ON_GREEN,
        relief=tk.FLAT, bd=0, cursor="hand2",
        font=BODY_BOLD, padx=18, pady=8,
        **kwargs,
    )
    btn.bind("<Enter>", lambda e: btn.config(bg=GREEN_DARK))
    btn.bind("<Leave>", lambda e: btn.config(bg=GREEN_MID))
    return btn


def secondary_button(parent, text: str, command, **kwargs) -> tk.Button:
    """An outlined / subtle button for secondary actions."""
    btn = tk.Button(
        parent, text=text, command=command,
        bg=SURFACE, fg=GREEN_DARK,
        activebackground=GREEN_LIGHT, activeforeground=GREEN_DARK,
        relief=tk.SOLID, bd=1, cursor="hand2",
        font=BODY, padx=14, pady=7,
        highlightbackground=BORDER,
        **kwargs,
    )
    btn.bind("<Enter>", lambda e: btn.config(bg=GREEN_LIGHT))
    btn.bind("<Leave>", lambda e: btn.config(bg=SURFACE))
    return btn


def entry(parent, textvariable, width: int = 40) -> tk.Entry:
    """A flat, bordered text entry."""
    return tk.Entry(
        parent, textvariable=textvariable, width=width,
        bg=BG, fg=TEXT, insertbackground=GREEN_DARK,
        relief=tk.SOLID, bd=1, font=BODY,
        highlightthickness=1, highlightbackground=BORDER,
        highlightcolor=GREEN_MID,
    )
