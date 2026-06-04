"""Parameter configuration UI for siteval.

A self-contained Tkinter frame (embeddable in the unified app) that lets the
user configure all Esri Wayback download parameters before a run. Returns a
dataclass of validated settings via ``ParamsUI.get()``.

Temporal model
--------------
The user sets three values:
  back     — how far *before* the target date to look  (value + unit)
  forward  — how far *after*  the target date to look  (value + unit)
  interval — step between sample dates                 (value + unit)

The number of images is derived automatically and shown live.

Examples
--------
  back=1yr, forward=1yr, interval=1yr  → 3 images: −1yr, 0, +1yr
  back=2yr, forward=0,   interval=1yr  → 3 images: −2yr, −1yr, 0
  back=0,   forward=6mo, interval=6mo  → 2 images: 0, +6mo
"""

from __future__ import annotations

import tkinter as tk
from dataclasses import dataclass
from tkinter import filedialog

from . import theme as T

_UNITS = ["days", "months", "years"]
_UNIT_DAYS: dict[str, float] = {"days": 1.0, "months": 30.4375, "years": 365.25}


def _to_days(value: float, unit: str) -> float:
    return value * _UNIT_DAYS[unit]


def _fmt_days(days: float) -> str:
    """Format a day count as a human-readable offset label."""
    if days == 0:
        return "0"
    sign = "+" if days > 0 else "−"
    d = abs(days)
    if d >= 365.25 * 0.9:
        return f"{sign}{d / 365.25:.4g} yr"
    if d >= 30.4375 * 0.9:
        return f"{sign}{d / 30.4375:.4g} mo"
    return f"{sign}{d:.4g} d"


def _compute_offsets(back_days: float, forward_days: float,
                     interval_days: float) -> list[float]:
    """Return the list of day-offsets relative to the target date."""
    if interval_days <= 0:
        return [0.0]
    offsets: list[float] = []
    current = -back_days
    limit = forward_days + interval_days * 0.01
    while current <= limit:
        offsets.append(round(current, 6))
        current += interval_days
    return offsets if offsets else [0.0]


@dataclass
class DownloadParams:
    csv_path: str
    output_dir: str
    back_days: float
    forward_days: float
    interval_days: float
    zoom: int
    tile_size: int


class ParamsUI(tk.Frame):
    """Tkinter frame for configuring siteval download parameters."""

    def __init__(self, parent, **kwargs):
        super().__init__(parent, bg=T.BG, **kwargs)
        self._build()

    # ── UI helpers ──────────────────────────────────────────────────────

    def _card(self, title: str) -> tk.Frame:
        outer = tk.Frame(self, bg=T.BG)
        outer.pack(fill=tk.X, pady=(0, 12))
        bar = tk.Frame(outer, bg=T.GREEN, width=4)
        bar.pack(side=tk.LEFT, fill=tk.Y)
        body = tk.Frame(outer, bg=T.SURFACE,
                        highlightbackground=T.BORDER, highlightthickness=1)
        body.pack(side=tk.LEFT, fill=tk.X, expand=True)
        tk.Label(body, text=title, bg=T.SURFACE, fg=T.GREEN_DARK,
                 font=T.H3).pack(anchor='w', padx=14, pady=(10, 6))
        inner = tk.Frame(body, bg=T.SURFACE)
        inner.pack(fill=tk.X, padx=14, pady=(0, 12))
        return inner

    def _row(self, parent) -> tk.Frame:
        r = tk.Frame(parent, bg=T.SURFACE)
        r.pack(fill=tk.X, pady=3)
        return r

    def _label(self, parent, text: str, width: int = 18) -> tk.Label:
        return tk.Label(parent, text=text, bg=T.SURFACE, fg=T.TEXT,
                        font=T.BODY, width=width, anchor='w')

    def _hint(self, parent, text: str) -> tk.Label:
        return tk.Label(parent, text=text, bg=T.SURFACE, fg=T.TEXT_MUTED,
                        font=T.SMALL)

    def _spinbox(self, parent, var, from_, to, increment=1.0, width=5):
        return tk.Spinbox(
            parent, from_=from_, to=to, increment=increment,
            textvariable=var, width=width,
            bg=T.BG, fg=T.TEXT, buttonbackground=T.GREEN_LIGHT,
            relief=tk.SOLID, bd=1, font=T.BODY,
            highlightthickness=1, highlightbackground=T.BORDER,
            highlightcolor=T.GREEN_MID,
            command=self._update_preview,
        )

    def _unit_menu(self, parent, var: tk.StringVar) -> tk.OptionMenu:
        menu = tk.OptionMenu(parent, var, *_UNITS,
                             command=lambda _: self._update_preview())
        menu.config(bg=T.BG, fg=T.TEXT, activebackground=T.GREEN_LIGHT,
                    activeforeground=T.GREEN_DARK, relief=tk.SOLID, bd=1,
                    font=T.BODY, width=7, highlightthickness=0)
        menu["menu"].config(bg=T.BG, fg=T.TEXT, font=T.BODY,
                            activebackground=T.GREEN_MID,
                            activeforeground=T.ON_GREEN)
        return menu

    def _radio(self, parent, text, var, value):
        return tk.Radiobutton(
            parent, text=text, variable=var, value=value,
            bg=T.SURFACE, fg=T.TEXT, selectcolor=T.BG,
            activebackground=T.SURFACE, activeforeground=T.GREEN_DARK,
            font=T.BODY, cursor="hand2",
        )

    # ── Build ────────────────────────────────────────────────────────────

    def _build(self):
        # ── 1. File paths ──
        paths = self._card("1.  File paths")

        csv_row = self._row(paths)
        self._label(csv_row, "Input CSV").pack(side=tk.LEFT)
        self._csv_var = tk.StringVar()
        T.entry(csv_row, self._csv_var, width=42).pack(side=tk.LEFT, padx=(0, 6))
        T.secondary_button(csv_row, "Browse…", self._browse_csv).pack(side=tk.LEFT)

        out_row = self._row(paths)
        self._label(out_row, "Output directory").pack(side=tk.LEFT)
        self._out_var = tk.StringVar(value="output")
        T.entry(out_row, self._out_var, width=42).pack(side=tk.LEFT, padx=(0, 6))
        T.secondary_button(out_row, "Browse…", self._browse_output).pack(side=tk.LEFT)

        # ── 2. Temporal parameters ──
        temporal = self._card("2.  Temporal sampling")
        self._hint(
            temporal,
            "Images are sampled at a fixed interval across a window around "
            "each point's target date.",
        ).pack(anchor='w', pady=(0, 8))

        back_row = self._row(temporal)
        self._label(back_row, "Look back").pack(side=tk.LEFT)
        self._back_val = tk.DoubleVar(value=1.0)
        self._spinbox(back_row, self._back_val, 0, 100).pack(side=tk.LEFT, padx=(0, 4))
        self._back_unit = tk.StringVar(value="years")
        self._unit_menu(back_row, self._back_unit).pack(side=tk.LEFT, padx=(0, 10))
        self._hint(back_row, "← before the target date").pack(side=tk.LEFT)

        fwd_row = self._row(temporal)
        self._label(fwd_row, "Look forward").pack(side=tk.LEFT)
        self._fwd_val = tk.DoubleVar(value=1.0)
        self._spinbox(fwd_row, self._fwd_val, 0, 100).pack(side=tk.LEFT, padx=(0, 4))
        self._fwd_unit = tk.StringVar(value="years")
        self._unit_menu(fwd_row, self._fwd_unit).pack(side=tk.LEFT, padx=(0, 10))
        self._hint(fwd_row, "→ after the target date").pack(side=tk.LEFT)

        int_row = self._row(temporal)
        self._label(int_row, "Interval").pack(side=tk.LEFT)
        self._int_val = tk.DoubleVar(value=1.0)
        self._spinbox(int_row, self._int_val, 0.5, 100, increment=0.5).pack(
            side=tk.LEFT, padx=(0, 4))
        self._int_unit = tk.StringVar(value="years")
        self._unit_menu(int_row, self._int_unit).pack(side=tk.LEFT, padx=(0, 10))
        self._hint(int_row, "step between images").pack(side=tk.LEFT)

        # Live preview
        preview = tk.Frame(temporal, bg=T.GREEN_LIGHT,
                           highlightbackground=T.GREEN_TINT, highlightthickness=1)
        preview.pack(fill=tk.X, pady=(10, 0))
        self._preview_count = tk.Label(
            preview, text="", bg=T.GREEN_LIGHT, fg=T.GREEN_DARK,
            font=T.BODY_BOLD, anchor='w',
        )
        self._preview_count.pack(anchor='w', padx=10, pady=(8, 2))
        self._preview_offsets = tk.Label(
            preview, text="", bg=T.GREEN_LIGHT, fg=T.TEXT,
            font=T.SMALL, anchor='w', wraplength=600, justify=tk.LEFT,
        )
        self._preview_offsets.pack(anchor='w', padx=10, pady=(0, 8))

        for var in (self._back_val, self._fwd_val, self._int_val):
            var.trace_add('write', lambda *_: self._update_preview())
        self._update_preview()

        # ── 3. Spatial parameters ──
        spatial = self._card("3.  Spatial scale")

        zoom_row = self._row(spatial)
        self._label(zoom_row, "Zoom level").pack(side=tk.LEFT)
        self._zoom_var = tk.IntVar(value=18)
        zoom_desc = {17: "17 · ~1.2 km", 18: "18 · ~600 m", 19: "19 · ~300 m"}
        for z in (17, 18, 19):
            self._radio(zoom_row, zoom_desc[z], self._zoom_var, z).pack(
                side=tk.LEFT, padx=(0, 12))

        tile_row = self._row(spatial)
        self._label(tile_row, "Tile grid").pack(side=tk.LEFT)
        self._tile_var = tk.IntVar(value=3)
        tile_opts = {1: "1×1 · 256 px", 3: "3×3 · 768 px", 5: "5×5 · 1280 px"}
        for t in (1, 3, 5):
            self._radio(tile_row, tile_opts[t], self._tile_var, t).pack(
                side=tk.LEFT, padx=(0, 12))

        # ── Error label ──
        self._error_label = tk.Label(self, text="", bg=T.BG, fg=T.REJECT,
                                     font=T.SMALL_BOLD, anchor='w')
        self._error_label.pack(fill=tk.X, pady=(2, 0))

    # ── Helpers ──────────────────────────────────────────────────────────

    def _browse_csv(self):
        path = filedialog.askopenfilename(
            title="Select input CSV",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
        )
        if path:
            self._csv_var.set(path)

    def _browse_output(self):
        path = filedialog.askdirectory(title="Select output directory")
        if path:
            self._out_var.set(path)

    def _update_preview(self):
        try:
            back_days = _to_days(float(self._back_val.get()), self._back_unit.get())
            fwd_days = _to_days(float(self._fwd_val.get()), self._fwd_unit.get())
            int_days = _to_days(float(self._int_val.get()), self._int_unit.get())
        except (ValueError, tk.TclError):
            self._preview_count.config(text="—")
            self._preview_offsets.config(text="")
            return

        offsets = _compute_offsets(back_days, fwd_days, int_days)
        n = len(offsets)
        self._preview_count.config(
            text=f"→  {n} image{'s' if n != 1 else ''} per point")
        self._preview_offsets.config(
            text="   ".join(_fmt_days(o) for o in offsets))

    # ── Public API ────────────────────────────────────────────────────────

    def get(self) -> DownloadParams | None:
        """Validate inputs and return a DownloadParams, or None on error."""
        csv_path = self._csv_var.get().strip()
        out_dir = self._out_var.get().strip()
        errors: list[str] = []

        if not csv_path:
            errors.append("Input CSV is required.")
        if not out_dir:
            errors.append("Output directory is required.")

        try:
            back_days = _to_days(float(self._back_val.get()), self._back_unit.get())
            if back_days < 0:
                errors.append("Look-back must be ≥ 0.")
        except (ValueError, tk.TclError):
            errors.append("Look-back must be a number.")
            back_days = 0.0

        try:
            fwd_days = _to_days(float(self._fwd_val.get()), self._fwd_unit.get())
            if fwd_days < 0:
                errors.append("Look-forward must be ≥ 0.")
        except (ValueError, tk.TclError):
            errors.append("Look-forward must be a number.")
            fwd_days = 0.0

        try:
            int_days = _to_days(float(self._int_val.get()), self._int_unit.get())
            if int_days <= 0:
                errors.append("Interval must be > 0.")
        except (ValueError, tk.TclError):
            errors.append("Interval must be a number.")
            int_days = 365.25

        if errors:
            self._error_label.config(text="⚠  " + "   ".join(errors))
            return None

        self._error_label.config(text="")
        return DownloadParams(
            csv_path=csv_path,
            output_dir=out_dir,
            back_days=back_days,
            forward_days=fwd_days,
            interval_days=int_days,
            zoom=self._zoom_var.get(),
            tile_size=self._tile_var.get(),
        )

    def set_csv_path(self, path: str):
        """Pre-fill the CSV path (called from the unified app after upload)."""
        self._csv_var.set(path)
