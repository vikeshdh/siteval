"""Tk-based imagery validator for siteval.

Presents each point's downloaded Esri Wayback imagery and records a ternary
decision -- ``accept``, ``reject``, or ``caution`` -- plus free-text notes,
to a CSV. Auto-saves on close and resumes on re-launch from the last
unvalidated point.

Used by the ``siteval validate`` CLI command and the unified app.
"""

from __future__ import annotations

import re
import sys
import tkinter as tk
from datetime import datetime
from pathlib import Path
from tkinter import messagebox, ttk

import pandas as pd
from PIL import Image, ImageTk

from . import theme as T

_DECISIONS = ("accept", "reject", "caution")
_DECISION_COLOR = {"accept": T.ACCEPT, "reject": T.REJECT, "caution": T.CAUTION}
# Foreground when a chip is selected — dark text on the light yellow chip.
_DECISION_FG = {"accept": T.ON_GREEN, "reject": T.ON_GREEN, "caution": "#1a1a1a"}
_DATE_RE = re.compile(r"(\d{4})-(\d{2})-(\d{2})")


def _extract_date(filename: str) -> tuple[str, str]:
    """Return (pretty_date, iso_date) parsed from an image filename.

    Filenames are ``<id>_<seq>_<YYYY-MM-DD>.png``. Falls back gracefully if
    no date is present.
    """
    m = _DATE_RE.search(filename)
    if not m:
        return ("date unknown", "")
    iso = m.group(0)
    try:
        dt = datetime.strptime(iso, "%Y-%m-%d")
        return (dt.strftime("%m-%d-%Y"), iso)  # e.g. "07-15-2020"
    except ValueError:
        return (iso, iso)


class ImageValidator:
    """GUI application for Accept / Reject / Caution validation of imagery."""

    def __init__(
        self,
        input_dir: str | Path,
        csv_path: str | Path,
        output_path: str | Path,
        master: tk.Misc | None = None,
    ):
        self.input_dir = Path(input_dir)
        self.csv_path = Path(csv_path)
        self.output_path = Path(output_path)

        self.df = pd.read_csv(self.csv_path)
        for col, default in [("notes", ""), ("validated", False), ("decision", "")]:
            if col not in self.df.columns:
                self.df[col] = default

        self.point_ids: list[str] = [
            str(pid)
            for pid in self.df['id']
            if (self.input_dir / str(pid)).exists()
            and any((self.input_dir / str(pid)).glob('*.png'))
        ]

        if not self.point_ids:
            print("No imagery found in input directory.")
            sys.exit(1)

        # Resume from first unvalidated point
        self.current_index = 0
        for i, pid in enumerate(self.point_ids):
            row = self.df[self.df['id'].astype(str) == pid].iloc[0]
            if not row.get('validated', False):
                self.current_index = i
                break

        self.image_refs: list[ImageTk.PhotoImage] = []

        # Use Toplevel when embedded inside an existing app so there is only
        # ever one tk.Tk() per process (multiple Tk roots break PhotoImage).
        self._standalone = master is None
        if self._standalone:
            self.root: tk.Tk | tk.Toplevel = tk.Tk()
        else:
            self.root = tk.Toplevel(master)
        self.root.title("siteval — imagery validator")
        self.root.geometry("1400x940")
        self.root.minsize(1000, 760)
        self.root.configure(bg=T.BG)
        T.apply_ttk_theme(self.root)

        self._setup_ui()
        self._load_current_point()

        self.root.bind('<Left>', lambda e: self.prev_point())
        self.root.bind('<Right>', lambda e: self.next_point())
        self.root.bind('<Control-s>', lambda e: self.save_and_continue())
        self.root.bind('<Return>', lambda e: self.save_and_continue())
        self.root.bind('<KeyPress-a>', self._shortcut_accept)
        self.root.bind('<KeyPress-A>', self._shortcut_accept)
        self.root.bind('<KeyPress-r>', self._shortcut_reject)
        self.root.bind('<KeyPress-R>', self._shortcut_reject)
        self.root.bind('<KeyPress-c>', self._shortcut_caution)
        self.root.bind('<KeyPress-C>', self._shortcut_caution)

    # ── Keyboard shortcuts ──────────────────────────────────────────────

    def _shortcut_accept(self, event):
        if self.root.focus_get() is not self.notes_text:
            self._set_decision('accept')

    def _shortcut_reject(self, event):
        if self.root.focus_get() is not self.notes_text:
            self._set_decision('reject')

    def _shortcut_caution(self, event):
        if self.root.focus_get() is not self.notes_text:
            self._set_decision('caution')

    def _set_decision(self, value: str):
        self.decision_var.set(value)
        self._update_decision_highlight()

    # ── UI setup ────────────────────────────────────────────────────────

    def _setup_ui(self):
        # ── Slim header band: point + coords on the left, progress right ──
        header = tk.Frame(self.root, bg=T.GREEN, height=38)
        header.pack(fill=tk.X)
        header.pack_propagate(False)

        self.title_label = tk.Label(
            header, text="", bg=T.GREEN, fg=T.ON_GREEN, font=T.BODY_BOLD,
        )
        self.title_label.pack(side=tk.LEFT, padx=(16, 10))

        self.info_label = tk.Label(
            header, text="", bg=T.GREEN, fg=T.GREEN_LIGHT, font=T.SMALL,
        )
        self.info_label.pack(side=tk.LEFT)

        self.progress_label = tk.Label(
            header, text="", bg=T.GREEN, fg=T.ON_GREEN, font=T.SMALL_BOLD,
        )
        self.progress_label.pack(side=tk.RIGHT, padx=16)

        main = tk.Frame(self.root, bg=T.BG, padx=14, pady=8)
        main.pack(fill=tk.BOTH, expand=True)

        # ── Image area with horizontal scrollbar ──
        img_outer = tk.Frame(main, bg=T.SURFACE_ALT,
                             highlightbackground=T.BORDER, highlightthickness=1)
        img_outer.pack(fill=tk.BOTH, expand=True)

        self.canvas = tk.Canvas(img_outer, bg=T.SURFACE_ALT, highlightthickness=0)
        h_scroll = ttk.Scrollbar(img_outer, orient=tk.HORIZONTAL,
                                  command=self.canvas.xview,
                                  style="Siteval.Horizontal.TScrollbar")
        self.canvas.configure(xscrollcommand=h_scroll.set)
        h_scroll.pack(side=tk.BOTTOM, fill=tk.X)
        self.canvas.pack(fill=tk.BOTH, expand=True)

        self.img_frame = tk.Frame(self.canvas, bg=T.SURFACE_ALT)
        self.canvas.create_window((0, 0), window=self.img_frame, anchor='nw')
        self.img_frame.bind(
            '<Configure>',
            lambda e: self.canvas.configure(scrollregion=self.canvas.bbox('all')),
        )
        # Re-fit image sizes to the available height when the window resizes.
        self.canvas.bind('<Configure>', self._on_canvas_resize)

        # ── Decision & notes panel (compact, single inner pad) ──
        panel = tk.Frame(main, bg=T.SURFACE,
                         highlightbackground=T.BORDER, highlightthickness=1)
        panel.pack(fill=tk.X, pady=(8, 0))

        inner = tk.Frame(panel, bg=T.SURFACE)
        inner.pack(fill=tk.X, padx=12, pady=8)

        # Row 1: decision chips (left)  +  navigation buttons (right)
        row1 = tk.Frame(inner, bg=T.SURFACE)
        row1.pack(fill=tk.X)

        tk.Label(row1, text="Decision", bg=T.SURFACE, fg=T.TEXT,
                 font=T.H3).pack(side=tk.LEFT, padx=(0, 10))

        self.decision_var = tk.StringVar(value='')
        self._decision_btns: dict[str, tk.Label] = {}
        chips = {'accept': ('Accept', 'A'), 'reject': ('Reject', 'R'),
                 'caution': ('Caution', 'C')}
        for val, (label, key) in chips.items():
            chip = tk.Label(
                row1, text=f"{label} ({key})",
                bg=T.BG, fg=T.TEXT_MUTED,
                font=T.BODY_BOLD, padx=14, pady=6, cursor="hand2",
                highlightbackground=T.BORDER, highlightthickness=1,
            )
            chip.pack(side=tk.LEFT, padx=(0, 6))
            chip.bind('<Button-1>', lambda e, v=val: self._set_decision(v))
            self._decision_btns[val] = chip

        # Navigation buttons live on the right of the same row.
        T.primary_button(row1, "Save & exit", self.save_and_exit).pack(
            side=tk.RIGHT)
        T.secondary_button(row1, "Skip", self.next_point).pack(
            side=tk.RIGHT, padx=(0, 6))
        T.secondary_button(row1, "Next →", self.next_point).pack(
            side=tk.RIGHT, padx=(0, 6))
        T.primary_button(row1, "Save & next (Enter)",
                        self.save_and_continue).pack(side=tk.RIGHT, padx=(0, 6))
        T.secondary_button(row1, "← Previous", self.prev_point).pack(
            side=tk.RIGHT, padx=(0, 6))

        # Row 2: compact notes field with inline label.
        row2 = tk.Frame(inner, bg=T.SURFACE)
        row2.pack(fill=tk.X, pady=(8, 0))
        tk.Label(row2, text="Notes", bg=T.SURFACE, fg=T.TEXT,
                 font=T.H3).pack(side=tk.LEFT, padx=(0, 10), anchor='n')
        self.notes_text = tk.Text(
            row2, height=2, font=T.BODY, wrap=tk.WORD,
            bg=T.BG, fg=T.TEXT, insertbackground=T.GREEN_DARK,
            relief=tk.SOLID, bd=1,
            highlightthickness=1, highlightbackground=T.BORDER,
            highlightcolor=T.GREEN_MID,
        )
        self.notes_text.pack(side=tk.LEFT, fill=tk.X, expand=True)

        # ── Status bar ──
        self.status_var = tk.StringVar(
            value="Ready — A to Accept · R to Reject · C for Caution"
        )
        tk.Label(
            self.root, textvariable=self.status_var,
            bg=T.SURFACE_ALT, fg=T.TEXT_MUTED, anchor=tk.W,
            font=T.SMALL, padx=12, pady=4,
        ).pack(fill=tk.X, side=tk.BOTTOM)

    def _update_decision_highlight(self):
        """Colour the active decision chip to reflect the chosen state."""
        current = self.decision_var.get()
        for val, chip in self._decision_btns.items():
            if val == current:
                chip.configure(bg=_DECISION_COLOR[val], fg=_DECISION_FG[val],
                               highlightbackground=_DECISION_COLOR[val])
            else:
                chip.configure(bg=T.BG, fg=T.TEXT_MUTED,
                               highlightbackground=T.BORDER)

    # ── Point loading ───────────────────────────────────────────────────

    def _load_current_point(self):
        if not self.point_ids:
            return

        point_id = self.point_ids[self.current_index]
        point_dir = self.input_dir / point_id

        self.title_label.config(text=point_id)
        self.progress_label.config(
            text=f"{self.current_index + 1} / {len(self.point_ids)}"
        )

        mask = self.df['id'].astype(str) == point_id
        point_row = self.df[mask].iloc[0]

        parts = [
            f"{float(point_row['lat']):.5f}, {float(point_row['lon']):.5f}",
        ]
        if 'target_date' in self.df.columns:
            parts.append(f"target {point_row['target_date']}")
        elif 'target_year' in self.df.columns:
            parts.append(f"target {point_row['target_year']}")
        self.info_label.config(text="   ·   ".join(parts))

        self.notes_text.delete('1.0', tk.END)
        notes = point_row.get('notes', '')
        if pd.notna(notes) and notes:
            self.notes_text.insert('1.0', str(notes))

        existing = point_row.get('decision', '')
        self.decision_var.set(
            existing if pd.notna(existing) and existing in _DECISIONS else ''
        )
        self._update_decision_highlight()

        for widget in self.img_frame.winfo_children():
            widget.destroy()
        self.image_refs.clear()

        image_files = sorted(point_dir.glob('*.png'))
        if not image_files:
            tk.Label(self.img_frame, text="No images found for this point",
                     bg=T.SURFACE_ALT, fg=T.TEXT_MUTED, font=T.BODY).pack(
                padx=20, pady=20)
            return

        thumb = self._thumb_size()
        for idx, img_path in enumerate(image_files):
            pretty_date, iso_date = _extract_date(img_path.name)

            cell = tk.Frame(self.img_frame, bg=T.BG,
                            highlightbackground=T.BORDER, highlightthickness=1)
            cell.grid(row=0, column=idx, padx=6, pady=6, sticky='n')

            # Date header badge — green bar above each image.
            date_badge = tk.Label(
                cell, text=f"📅  {pretty_date}", bg=T.GREEN, fg=T.ON_GREEN,
                font=T.BODY_BOLD, anchor='center', pady=5,
            )
            date_badge.pack(fill=tk.X)

            body = tk.Frame(cell, bg=T.BG, padx=4, pady=4)
            body.pack()
            try:
                img = Image.open(img_path)
                img.thumbnail(thumb, Image.Resampling.LANCZOS)
                photo = ImageTk.PhotoImage(img)
                self.image_refs.append(photo)
                tk.Label(body, image=photo, bg=T.BG).pack()
                # Sequence position within this point (oldest → newest).
                tk.Label(body, text=f"capture {idx + 1} of {len(image_files)}",
                         bg=T.BG, fg=T.TEXT_MUTED, font=T.SMALL).pack(pady=(3, 0))
            except Exception:
                tk.Label(body, text=f"Error:\n{img_path.name}",
                         bg=T.BG, fg=T.REJECT, font=T.SMALL).pack()

        self.img_frame.update_idletasks()
        self.canvas.configure(scrollregion=self.canvas.bbox('all'))
        self.status_var.set(
            f"{len(image_files)} Wayback captures for {point_id}  ·  "
            "oldest → newest, left to right"
        )

    def _thumb_size(self) -> tuple[int, int]:
        """Largest thumbnail that fits the current image-canvas height.

        Source composites are 768–1280 px, so we never upscale past native
        resolution — images stay crisp while filling the available space.
        """
        self.canvas.update_idletasks()
        avail_h = self.canvas.winfo_height()
        if avail_h < 80:            # canvas not realised yet — sensible default
            avail_h = 620
        # Reserve room for the date badge (~34 px) + caption (~22 px) + pad.
        target = max(360, avail_h - 70)
        target = min(target, 1100)  # cap so 5×5 grids don't become huge
        return (target, target)

    def _on_canvas_resize(self, event):
        """Re-fit images to the new height, debounced to avoid thrash."""
        self.canvas.configure(scrollregion=self.canvas.bbox('all'))
        if getattr(self, '_resize_job', None):
            self.root.after_cancel(self._resize_job)
        self._resize_job = self.root.after(180, self._reflow_images)

    def _reflow_images(self):
        self._resize_job = None
        self._load_current_point()

    # ── Save / navigation ───────────────────────────────────────────────

    def _save_current(self):
        if not self.point_ids:
            return
        point_id = self.point_ids[self.current_index]
        notes = self.notes_text.get('1.0', tk.END).strip()
        decision = self.decision_var.get()

        mask = self.df['id'].astype(str) == point_id
        self.df.loc[mask, 'notes'] = notes
        self.df.loc[mask, 'decision'] = decision
        self.df.loc[mask, 'validated'] = bool(decision)

        label = {"accept": "Accepted", "reject": "Rejected",
                 "caution": "Caution flagged"}.get(decision, "")
        if label:
            self.status_var.set(f"{label}: {point_id}")
        else:
            self.status_var.set(f"Notes saved for {point_id} (no decision set)")

    def save_and_continue(self):
        self._save_current()
        self.next_point()

    def next_point(self):
        if self.current_index < len(self.point_ids) - 1:
            self.current_index += 1
            self._load_current_point()
            self.notes_text.focus_set()
        else:
            messagebox.showinfo("End", "You've reached the last point!")

    def prev_point(self):
        if self.current_index > 0:
            self.current_index -= 1
            self._load_current_point()
            self.notes_text.focus_set()

    def save_csv(self):
        self.output_path.parent.mkdir(parents=True, exist_ok=True)
        self.df.to_csv(self.output_path, index=False)
        self.status_var.set(f"Saved to {self.output_path}")

    def save_and_exit(self):
        self._save_current()
        self.save_csv()
        validated = int(self.df['validated'].sum())
        total = len(self.point_ids)
        messagebox.showinfo(
            "Saved",
            f"Results saved to:\n{self.output_path}\n\n"
            f"Validated: {validated} / {total} points",
        )
        self.root.destroy()

    def on_closing(self):
        if messagebox.askyesno("Save?", "Save validation results before closing?"):
            self._save_current()
            self.save_csv()
        self.root.destroy()

    def run(self):
        self.notes_text.focus_set()
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        if self._standalone:
            self.root.mainloop()
        else:
            # Parent already has a running event loop; block until this window
            # closes without starting a nested mainloop.
            self.root.wait_window()
