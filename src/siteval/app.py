"""Unified GUI launcher for siteval.

Drives the full 4-step workflow in a single window, using Esri Wayback
imagery as the source:

    Step 1 — Upload CSV
    Step 2 — Configure parameters
    Step 3 — Download imagery  (with live progress)
    Step 4 — Validate imagery  (opens the validator)

Entry point: ``siteval run``  or  ``python -m siteval.app``
"""

from __future__ import annotations

import logging
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from . import theme as T
from .downloader import WaybackDownloader
from .params_ui import ParamsUI
from .utils import load_points
from .validator import ImageValidator

logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s  %(levelname)s  %(message)s')


class SitevalApp:
    """Main application window — orchestrates the 4-step workflow."""

    def __init__(self):
        self.root = tk.Tk()
        self.root.title("siteval — Esri Wayback imagery download & validation")
        self.root.geometry("960x820")
        self.root.minsize(820, 700)
        self.root.configure(bg=T.BG)
        T.apply_ttk_theme(self.root)

        self._csv_path: str | None = None
        self._output_dir: str | None = None
        self._current_step = 1

        self._build_ui()
        self._go_to_step(1)

    # ── UI scaffold ─────────────────────────────────────────────────────

    def _build_ui(self):
        # ── Header band ──
        header = tk.Frame(self.root, bg=T.GREEN, height=72)
        header.pack(fill=tk.X)
        header.pack_propagate(False)

        brand = tk.Frame(header, bg=T.GREEN)
        brand.pack(side=tk.LEFT, padx=24)
        tk.Label(
            brand, text="siteval", bg=T.GREEN, fg=T.ON_GREEN, font=T.H1,
        ).pack(side=tk.LEFT, pady=14)
        tk.Label(
            brand, text="  satellite site validation",
            bg=T.GREEN, fg=T.GREEN_TINT, font=T.BODY,
        ).pack(side=tk.LEFT, pady=(22, 14))

        tk.Label(
            header,
            text="Imagery source: Esri Wayback",
            bg=T.GREEN, fg=T.GREEN_LIGHT, font=T.SMALL,
        ).pack(side=tk.RIGHT, padx=24)

        # ── Step indicator ──
        self._step_bar = tk.Frame(self.root, bg=T.SURFACE, height=54)
        self._step_bar.pack(fill=tk.X)
        self._step_bar.pack_propagate(False)

        inner = tk.Frame(self._step_bar, bg=T.SURFACE)
        inner.pack(pady=10)

        self._step_chips: list[tuple[tk.Label, tk.Label]] = []
        step_names = ["Upload CSV", "Parameters", "Download", "Validate"]
        for i, name in enumerate(step_names):
            chip = tk.Frame(inner, bg=T.SURFACE)
            chip.pack(side=tk.LEFT, padx=4)
            num = tk.Label(
                chip, text=str(i + 1), width=3,
                bg=T.BORDER, fg=T.TEXT_MUTED, font=T.SMALL_BOLD,
                padx=2, pady=2,
            )
            num.pack(side=tk.LEFT)
            txt = tk.Label(
                chip, text=name, bg=T.SURFACE, fg=T.TEXT_MUTED, font=T.SMALL_BOLD,
                padx=8,
            )
            txt.pack(side=tk.LEFT)
            self._step_chips.append((num, txt))
            if i < len(step_names) - 1:
                tk.Label(inner, text="→", bg=T.SURFACE, fg=T.TEXT_FAINT,
                         font=T.BODY).pack(side=tk.LEFT, padx=2)

        ttk.Separator(self.root, orient=tk.HORIZONTAL,
                      style="Siteval.TSeparator").pack(fill=tk.X)

        # ── Footer nav ──  (packed BEFORE the expanding content so it always
        # reserves space at the bottom and is never pushed off-screen).
        nav = tk.Frame(self.root, bg=T.BG, height=64)
        nav.pack(fill=tk.X, side=tk.BOTTOM)
        nav.pack_propagate(False)
        ttk.Separator(self.root, orient=tk.HORIZONTAL,
                      style="Siteval.TSeparator").pack(fill=tk.X, side=tk.BOTTOM)

        self._back_btn = T.secondary_button(nav, "← Back", self._back)
        self._back_btn.pack(side=tk.LEFT, padx=24, pady=12)

        self._next_btn = T.primary_button(nav, "Next →", self._next)
        self._next_btn.pack(side=tk.RIGHT, padx=24, pady=12)

        self._status_var = tk.StringVar(value="")
        tk.Label(
            nav, textvariable=self._status_var,
            bg=T.BG, fg=T.TEXT_MUTED, font=T.SMALL,
        ).pack(side=tk.LEFT, padx=8)

        # ── Content area ──  (scrollable; packed last so it fills the middle).
        outer = tk.Frame(self.root, bg=T.BG)
        outer.pack(fill=tk.BOTH, expand=True)

        self._content_canvas = tk.Canvas(outer, bg=T.BG, highlightthickness=0)
        vscroll = ttk.Scrollbar(outer, orient=tk.VERTICAL,
                                command=self._content_canvas.yview,
                                style="Siteval.Vertical.TScrollbar")
        self._content_canvas.configure(yscrollcommand=vscroll.set)
        vscroll.pack(side=tk.RIGHT, fill=tk.Y)
        self._content_canvas.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # The frame the step builders populate (28px gutters left & right).
        self._content = tk.Frame(self._content_canvas, bg=T.BG)
        self._content_window = self._content_canvas.create_window(
            (28, 18), window=self._content, anchor='nw')

        # Keep scrollregion in sync and make the inner frame match canvas width.
        self._content.bind(
            '<Configure>',
            lambda e: self._content_canvas.configure(
                scrollregion=self._content_canvas.bbox('all')),
        )
        self._content_canvas.bind(
            '<Configure>',
            lambda e: self._content_canvas.itemconfigure(
                self._content_window, width=e.width - 56),
        )

        # Mouse-wheel scrolling, scoped to when the cursor is over the canvas.
        self._content_canvas.bind('<Enter>', self._bind_mousewheel)
        self._content_canvas.bind('<Leave>', self._unbind_mousewheel)

    # ── Mouse-wheel helpers ─────────────────────────────────────────────

    def _bind_mousewheel(self, _event=None):
        self._content_canvas.bind_all('<MouseWheel>', self._on_mousewheel)

    def _unbind_mousewheel(self, _event=None):
        self._content_canvas.unbind_all('<MouseWheel>')

    def _on_mousewheel(self, event):
        self._content_canvas.yview_scroll(int(-event.delta / 120), "units")

    # ── Step management ─────────────────────────────────────────────────

    def _go_to_step(self, step: int):
        self._current_step = step
        self._refresh_step_bar()
        for widget in self._content.winfo_children():
            widget.destroy()

        builders = {1: self._build_step1, 2: self._build_step2,
                    3: self._build_step3, 4: self._build_step4}
        builders[step]()

        # Reset scroll position to the top for the new step.
        self._content.update_idletasks()
        self._content_canvas.configure(scrollregion=self._content_canvas.bbox('all'))
        self._content_canvas.yview_moveto(0)

        self._back_btn.config(state=tk.NORMAL if step > 1 else tk.DISABLED)
        self._next_btn.config(
            text="Start download →" if step == 2 else
                 "Open validator →" if step == 3 else
                 "Next →",
            state=tk.NORMAL,
        )
        if step == 4:
            self._next_btn.config(state=tk.DISABLED)

    def _refresh_step_bar(self):
        for i, (num, txt) in enumerate(self._step_chips):
            step_num = i + 1
            if step_num < self._current_step:
                num.config(bg=T.GREEN_MID, fg=T.ON_GREEN)
                txt.config(fg=T.GREEN_DARK)
            elif step_num == self._current_step:
                num.config(bg=T.GREEN, fg=T.ON_GREEN)
                txt.config(fg=T.GREEN_DARK)
            else:
                num.config(bg=T.BORDER, fg=T.TEXT_MUTED)
                txt.config(fg=T.TEXT_MUTED)

    def _back(self):
        if self._current_step > 1:
            self._go_to_step(self._current_step - 1)

    def _next(self):
        if self._current_step == 1:
            self._finish_step1()
        elif self._current_step == 2:
            self._finish_step2()
        elif self._current_step == 3:
            self._finish_step3()

    # ── helpers ──────────────────────────────────────────────────────────

    def _heading(self, parent, title: str, subtitle: str = "") -> tk.Frame:
        box = tk.Frame(parent, bg=T.BG)
        box.pack(fill=tk.X, pady=(0, 14))
        tk.Label(box, text=title, bg=T.BG, fg=T.TEXT, font=T.H2).pack(anchor='w')
        if subtitle:
            tk.Label(box, text=subtitle, bg=T.BG, fg=T.TEXT_MUTED,
                     font=T.SMALL).pack(anchor='w', pady=(2, 0))
        return box

    # ── Step 1: Upload CSV ──────────────────────────────────────────────

    def _build_step1(self):
        frame = tk.Frame(self._content, bg=T.BG)
        frame.pack(fill=tk.BOTH, expand=True)

        self._heading(
            frame, "Upload your points CSV",
            "Required columns:  id  ·  lat  ·  lon  ·  "
            "target_date (YYYY-MM-DD)  or  target_year",
        )

        # Drop / browse card
        drop = tk.Frame(frame, bg=T.GREEN_LIGHT, height=170,
                        highlightbackground=T.GREEN_MID, highlightthickness=2)
        drop.pack(fill=tk.X, pady=(0, 14))
        drop.pack_propagate(False)

        inner = tk.Frame(drop, bg=T.GREEN_LIGHT)
        inner.pack(expand=True)
        tk.Label(inner, text="⬆", bg=T.GREEN_LIGHT, fg=T.GREEN_MID,
                 font=(T.FONT_FAMILY, 30)).pack()
        self._csv_drop_label = tk.Label(
            inner, text="Click here to browse for a CSV file",
            bg=T.GREEN_LIGHT, fg=T.GREEN_DARK, font=T.BODY_BOLD,
        )
        self._csv_drop_label.pack(pady=(6, 0))
        for w in (drop, inner, self._csv_drop_label):
            w.bind('<Button-1>', lambda e: self._browse_csv())
            w.config(cursor="hand2")

        # Selected path
        path_row = tk.Frame(frame, bg=T.BG)
        path_row.pack(fill=tk.X, pady=(0, 4))
        tk.Label(path_row, text="Selected file:", bg=T.BG, fg=T.TEXT_MUTED,
                 font=T.SMALL_BOLD).pack(side=tk.LEFT)
        self._csv_path_label = tk.Label(
            path_row, text=self._csv_path or "(none yet)",
            bg=T.BG, fg=T.GREEN_DARK if self._csv_path else T.TEXT_FAINT,
            font=T.SMALL,
        )
        self._csv_path_label.pack(side=tk.LEFT, padx=6)

        # Preview card
        self._preview_frame = tk.Frame(frame, bg=T.BG)
        self._preview_frame.pack(fill=tk.BOTH, expand=True, pady=(6, 0))
        if self._csv_path:
            self._show_csv_preview(self._csv_path)

    def _browse_csv(self):
        path = filedialog.askopenfilename(
            title="Select points CSV",
            filetypes=[("CSV files", "*.csv"), ("All files", "*.*")],
        )
        if path:
            self._csv_path = path
            self._csv_path_label.config(text=path, fg=T.GREEN_DARK)
            self._csv_drop_label.config(text=Path(path).name)
            self._show_csv_preview(path)

    def _show_csv_preview(self, path: str):
        for w in self._preview_frame.winfo_children():
            w.destroy()
        try:
            df = load_points(path)
        except (FileNotFoundError, ValueError) as e:
            tk.Label(self._preview_frame, text=f"⚠  {e}", bg=T.BG,
                     fg=T.REJECT, font=T.SMALL_BOLD, wraplength=820,
                     justify=tk.LEFT).pack(anchor='w', pady=(4, 0))
            return

        card = tk.Frame(self._preview_frame, bg=T.SURFACE,
                        highlightbackground=T.BORDER, highlightthickness=1)
        card.pack(fill=tk.BOTH, expand=True)
        tk.Label(
            card,
            text=f"✓  {len(df)} points detected",
            bg=T.SURFACE, fg=T.GREEN_DARK, font=T.BODY_BOLD,
        ).pack(anchor='w', padx=12, pady=(10, 2))
        tk.Label(
            card, text=f"Columns:  {',  '.join(df.columns)}",
            bg=T.SURFACE, fg=T.TEXT_MUTED, font=T.SMALL,
            wraplength=820, justify=tk.LEFT,
        ).pack(anchor='w', padx=12, pady=(0, 6))

        # Small data preview (first 5 rows, key columns)
        cols = [c for c in ("id", "lat", "lon", "target_date", "target_year")
                if c in df.columns]
        head = df[cols].head(5)
        table = tk.Frame(card, bg=T.SURFACE)
        table.pack(anchor='w', padx=12, pady=(0, 10))
        for j, col in enumerate(cols):
            tk.Label(table, text=col, bg=T.SURFACE, fg=T.GREEN_DARK,
                     font=T.SMALL_BOLD, padx=8, anchor='w').grid(
                row=0, column=j, sticky='w')
        for i, (_, row) in enumerate(head.iterrows(), start=1):
            for j, col in enumerate(cols):
                tk.Label(table, text=str(row[col]), bg=T.SURFACE,
                         fg=T.TEXT, font=T.SMALL, padx=8, anchor='w').grid(
                    row=i, column=j, sticky='w')

    def _finish_step1(self):
        if not self._csv_path:
            messagebox.showwarning("No CSV", "Please select a CSV file first.")
            return
        try:
            load_points(self._csv_path)
        except (FileNotFoundError, ValueError) as e:
            messagebox.showerror("Invalid CSV", str(e))
            return
        self._go_to_step(2)

    # ── Step 2: Parameters ──────────────────────────────────────────────

    def _build_step2(self):
        self._heading(
            self._content, "Configure download parameters",
            "Sampling Esri Wayback captures around each point's target date.",
        )
        self._params_ui = ParamsUI(self._content)
        self._params_ui.pack(fill=tk.BOTH, expand=True)
        if self._csv_path:
            self._params_ui.set_csv_path(self._csv_path)

    def _finish_step2(self):
        params = self._params_ui.get()
        if params is None:
            return
        self._download_params = params
        self._output_dir = params.output_dir
        self._go_to_step(3)
        self._start_download()

    # ── Step 3: Download ────────────────────────────────────────────────

    def _build_step3(self):
        frame = tk.Frame(self._content, bg=T.BG)
        frame.pack(fill=tk.BOTH, expand=True)

        self._heading(frame, "Downloading imagery",
                      "Fetching Esri Wayback tiles for each point…")

        self._dl_progress_var = tk.DoubleVar(value=0)
        ttk.Progressbar(
            frame, variable=self._dl_progress_var, maximum=100,
            mode='determinate', style="Siteval.Horizontal.TProgressbar",
        ).pack(fill=tk.X, pady=(0, 6))

        self._dl_count_label = tk.Label(
            frame, text="Starting…", bg=T.BG, fg=T.TEXT_MUTED, font=T.BODY,
        )
        self._dl_count_label.pack(anchor='w')

        log_card = tk.Frame(frame, bg=T.SURFACE,
                            highlightbackground=T.BORDER, highlightthickness=1)
        log_card.pack(fill=tk.BOTH, expand=True, pady=(12, 0))
        self._dl_log = tk.Text(
            log_card, height=16, bg=T.SURFACE, fg=T.TEXT,
            font=T.MONO, state=tk.DISABLED, wrap=tk.WORD,
            relief=tk.FLAT, padx=10, pady=8,
        )
        self._dl_log.pack(fill=tk.BOTH, expand=True)

        self._next_btn.config(state=tk.DISABLED)

    def _log(self, message: str):
        self._dl_log.config(state=tk.NORMAL)
        self._dl_log.insert(tk.END, message + "\n")
        self._dl_log.see(tk.END)
        self._dl_log.config(state=tk.DISABLED)

    def _start_download(self):
        p = self._download_params

        def run():
            downloader = WaybackDownloader(
                output_dir=p.output_dir,
                zoom=p.zoom,
                logs_dir=str(Path(p.output_dir) / "logs"),
                back_days=p.back_days,
                forward_days=p.forward_days,
                interval_days=p.interval_days,
                tile_size=p.tile_size,
            )

            def on_progress(current, total):
                pct = (current / total) * 100 if total else 0
                self.root.after(0, self._dl_progress_var.set, pct)
                self.root.after(0, self._dl_count_label.config,
                                {"text": f"Point {current} / {total}"})
                self.root.after(0, self._log, f"  ✓ point {current} / {total}")

            self.root.after(0, self._log, f"CSV: {p.csv_path}")
            self.root.after(0, self._log,
                            f"Window: −{p.back_days:.0f}d / +{p.forward_days:.0f}d   "
                            f"every {p.interval_days:.0f}d   "
                            f"zoom {p.zoom}   {p.tile_size}×{p.tile_size} grid")
            self.root.after(0, self._log, "Fetching Esri Wayback configuration…")

            stats = downloader.process_csv(p.csv_path, progress_callback=on_progress)

            if "error" in stats:
                self.root.after(0, self._log, f"ERROR: {stats['error']}")
                self.root.after(0, messagebox.showerror,
                                "Download failed", stats["error"])
                return

            summary = (f"Done — {stats['success']} succeeded, "
                       f"{stats['failed']} failed  (total {stats['total']})")
            self.root.after(0, self._log, summary)
            self.root.after(0, self._dl_count_label.config, {"text": summary})
            self.root.after(0, self._next_btn.config, {"state": tk.NORMAL})
            self.root.after(0, self._status_var.set,
                            "Download complete — click to validate")

        threading.Thread(target=run, daemon=True).start()

    def _finish_step3(self):
        self._go_to_step(4)
        self._open_validator()

    # ── Step 4: Validate ────────────────────────────────────────────────

    def _build_step4(self):
        frame = tk.Frame(self._content, bg=T.BG)
        frame.pack(fill=tk.BOTH, expand=True)

        self._heading(frame, "Validate imagery")

        card = tk.Frame(frame, bg=T.SURFACE,
                        highlightbackground=T.BORDER, highlightthickness=1)
        card.pack(fill=tk.X, pady=(0, 16))
        tk.Label(
            card,
            text="The validator window is now open in a separate window.",
            bg=T.SURFACE, fg=T.TEXT, font=T.BODY_BOLD, justify=tk.LEFT,
        ).pack(anchor='w', padx=14, pady=(12, 8))

        for key, colour, fg, desc in [
            ("A", T.ACCEPT, T.ON_GREEN, "Accept — imagery clearly matches the site"),
            ("R", T.REJECT, T.ON_GREEN, "Reject — imagery does not match"),
            ("C", T.CAUTION, "#1a1a1a", "Caution — uncertain, needs a second look"),
        ]:
            row = tk.Frame(card, bg=T.SURFACE)
            row.pack(anchor='w', padx=14, pady=2)
            tk.Label(row, text=f" {key} ", bg=colour, fg=fg,
                     font=T.SMALL_BOLD).pack(side=tk.LEFT)
            tk.Label(row, text=f"  {desc}", bg=T.SURFACE, fg=T.TEXT_MUTED,
                     font=T.SMALL).pack(side=tk.LEFT)

        tk.Label(
            card,
            text="←  →  or  Enter to navigate · results auto-save and resume.",
            bg=T.SURFACE, fg=T.TEXT_MUTED, font=T.SMALL,
        ).pack(anchor='w', padx=14, pady=(8, 12))

        T.primary_button(frame, "Re-open validator",
                         self._open_validator).pack(anchor='w', pady=(0, 12))

        if self._output_dir:
            tk.Label(frame, text=f"Output directory:  {self._output_dir}",
                     bg=T.BG, fg=T.TEXT_FAINT, font=T.SMALL).pack(anchor='w')

    def _open_validator(self):
        if not self._csv_path or not self._output_dir:
            messagebox.showerror("Missing paths", "CSV or output directory not set.")
            return
        out_path = Path(self._output_dir) / "validated_points.csv"
        try:
            validator = ImageValidator(
                input_dir=self._output_dir,
                csv_path=self._csv_path,
                output_path=out_path,
                master=self.root,
            )
            validator.run()
        except SystemExit:
            pass
        except Exception as e:
            messagebox.showerror("Validator error", str(e))

    # ── Run ──────────────────────────────────────────────────────────────

    def run(self):
        self.root.mainloop()


def main():
    SitevalApp().run()


if __name__ == "__main__":
    main()
