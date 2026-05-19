"""Tk-based binary validator for grassval.

Refactored from the standalone Task 2 `validator.py` into a reusable module.
Presents each point's downloaded imagery and records a binary decision —
``accept`` or ``reject`` — in a CSV. Auto-saves on close and resumes on
re-launch.

Used by the `grassval validate` CLI command.
"""

from __future__ import annotations

import sys
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, ttk

import pandas as pd
from PIL import Image, ImageTk


class ImageValidator:
    """GUI application for binary Accept/Reject validation of imagery."""

    def __init__(self, input_dir: str | Path, csv_path: str | Path,
                 output_path: str | Path):
        self.input_dir = Path(input_dir)
        self.csv_path = Path(csv_path)
        self.output_path = Path(output_path)

        self.df = pd.read_csv(self.csv_path)
        if 'notes' not in self.df.columns:
            self.df['notes'] = ''
        if 'validated' not in self.df.columns:
            self.df['validated'] = False
        if 'decision' not in self.df.columns:
            self.df['decision'] = ''  # '', 'accept', or 'reject'

        self.point_ids: list[str] = []
        for point_id in self.df['id']:
            point_dir = self.input_dir / str(point_id)
            if point_dir.exists() and any(point_dir.glob('*.png')):
                self.point_ids.append(point_id)

        if not self.point_ids:
            print("No imagery found in input directory!")
            sys.exit(1)

        self.current_index = 0
        self.image_refs: list[ImageTk.PhotoImage] = []

        self.root = tk.Tk()
        self.root.title("Imagery Validator (Accept / Reject)")
        self.root.geometry("1400x900")
        self.root.configure(bg='#2b2b2b')

        self._setup_ui()
        self._load_current_point()

        self.root.bind('<Left>', lambda e: self.prev_point())
        self.root.bind('<Right>', lambda e: self.next_point())
        self.root.bind('<Control-s>', lambda e: self.save_and_continue())
        self.root.bind('<Return>', lambda e: self.save_and_continue())
        self.root.bind('<KeyPress-a>', self._decision_shortcut_accept)
        self.root.bind('<KeyPress-A>', self._decision_shortcut_accept)
        self.root.bind('<KeyPress-r>', self._decision_shortcut_reject)
        self.root.bind('<KeyPress-R>', self._decision_shortcut_reject)

    def _decision_shortcut_accept(self, event):
        if self.root.focus_get() is not self.notes_text:
            self.decision_var.set('accept')

    def _decision_shortcut_reject(self, event):
        if self.root.focus_get() is not self.notes_text:
            self.decision_var.set('reject')

    def _setup_ui(self):
        main_frame = ttk.Frame(self.root, padding="10")
        main_frame.pack(fill=tk.BOTH, expand=True)

        style = ttk.Style()
        style.configure('Title.TLabel', font=('Helvetica', 14, 'bold'))
        style.configure('Info.TLabel', font=('Helvetica', 11))

        header_frame = ttk.Frame(main_frame)
        header_frame.pack(fill=tk.X, pady=(0, 10))

        self.title_label = ttk.Label(header_frame, text="", style='Title.TLabel')
        self.title_label.pack(side=tk.LEFT)

        self.progress_label = ttk.Label(header_frame, text="", style='Info.TLabel')
        self.progress_label.pack(side=tk.RIGHT)

        self.info_label = ttk.Label(main_frame, text="", style='Info.TLabel')
        self.info_label.pack(fill=tk.X, pady=(0, 10))

        img_container = ttk.Frame(main_frame)
        img_container.pack(fill=tk.BOTH, expand=True)

        self.canvas = tk.Canvas(img_container, bg='#1e1e1e', highlightthickness=0)
        self.canvas.pack(fill=tk.BOTH, expand=True)

        self.img_frame = ttk.Frame(self.canvas)
        self.canvas.create_window((0, 0), window=self.img_frame, anchor='nw')

        notes_frame = ttk.LabelFrame(main_frame, text="Decision & Notes",
                                     padding="10")
        notes_frame.pack(fill=tk.X, pady=(10, 0))

        decision_frame = ttk.Frame(notes_frame)
        decision_frame.pack(fill=tk.X, pady=(0, 8))

        ttk.Label(decision_frame, text="Decision:",
                  font=('Helvetica', 11, 'bold')).pack(side=tk.LEFT, padx=(0, 10))

        self.decision_var = tk.StringVar(value='')
        ttk.Radiobutton(decision_frame, text="Accept (A)", variable=self.decision_var,
                        value='accept').pack(side=tk.LEFT, padx=5)
        ttk.Radiobutton(decision_frame, text="Reject (R)", variable=self.decision_var,
                        value='reject').pack(side=tk.LEFT, padx=5)

        self.notes_text = tk.Text(notes_frame, height=3, font=('Helvetica', 11),
                                  wrap=tk.WORD)
        self.notes_text.pack(fill=tk.X, pady=(0, 10))

        btn_frame = ttk.Frame(notes_frame)
        btn_frame.pack(fill=tk.X)

        ttk.Button(btn_frame, text="< Previous (Left Arrow)",
                   command=self.prev_point).pack(side=tk.LEFT, padx=(0, 10))
        ttk.Button(btn_frame, text="Save & Next (Enter)",
                   command=self.save_and_continue).pack(side=tk.LEFT, padx=(0, 10))
        ttk.Button(btn_frame, text="Next > (Right Arrow)",
                   command=self.next_point).pack(side=tk.LEFT, padx=(0, 10))
        ttk.Button(btn_frame, text="Skip",
                   command=self.next_point).pack(side=tk.LEFT, padx=(0, 10))
        ttk.Button(btn_frame, text="Save CSV & Exit",
                   command=self.save_and_exit).pack(side=tk.RIGHT)

        self.status_var = tk.StringVar(
            value="Ready - press A to Accept or R to Reject"
        )
        status_bar = ttk.Label(main_frame, textvariable=self.status_var,
                               relief=tk.SUNKEN, anchor=tk.W)
        status_bar.pack(fill=tk.X, pady=(10, 0))

    def _load_current_point(self):
        if not self.point_ids:
            return

        point_id = self.point_ids[self.current_index]
        point_dir = self.input_dir / str(point_id)

        self.title_label.config(text=f"Point: {point_id}")
        self.progress_label.config(
            text=f"{self.current_index + 1} / {len(self.point_ids)}"
        )

        point_row = self.df[self.df['id'] == point_id].iloc[0]
        info_text = (
            f"Lat: {point_row['lat']:.6f}  |  "
            f"Lon: {point_row['lon']:.6f}  |  "
            f"Target Year: {point_row['target_year']}"
        )
        self.info_label.config(text=info_text)

        self.notes_text.delete('1.0', tk.END)
        if pd.notna(point_row.get('notes', '')) and point_row.get('notes', ''):
            self.notes_text.insert('1.0', str(point_row['notes']))

        existing_decision = point_row.get('decision', '')
        if pd.notna(existing_decision) and existing_decision in ('accept', 'reject'):
            self.decision_var.set(existing_decision)
        else:
            self.decision_var.set('')

        for widget in self.img_frame.winfo_children():
            widget.destroy()
        self.image_refs.clear()

        image_files = sorted(point_dir.glob('*.png'))
        if not image_files:
            ttk.Label(self.img_frame, text="No images found for this point").pack()
            return

        max_width = 320
        max_height = 400

        for idx, img_path in enumerate(image_files):
            cell = ttk.Frame(self.img_frame)
            cell.grid(row=0, column=idx, padx=5, pady=5)
            try:
                img = Image.open(img_path)
                img.thumbnail((max_width, max_height), Image.Resampling.LANCZOS)
                photo = ImageTk.PhotoImage(img)
                self.image_refs.append(photo)

                ttk.Label(cell, image=photo).pack()
                caption = img_path.stem.replace(f"{point_id}_", "")
                ttk.Label(cell, text=caption, font=('Helvetica', 9)).pack()
            except Exception:
                ttk.Label(cell, text=f"Error loading:\n{img_path.name}").pack()

        self.img_frame.update_idletasks()
        self.canvas.config(scrollregion=self.canvas.bbox('all'))
        self.status_var.set(f"Loaded {len(image_files)} images for {point_id}")

    def save_notes(self):
        if not self.point_ids:
            return
        point_id = self.point_ids[self.current_index]
        notes = self.notes_text.get('1.0', tk.END).strip()
        decision = self.decision_var.get()

        mask = self.df['id'] == point_id
        self.df.loc[mask, 'notes'] = notes
        self.df.loc[mask, 'decision'] = decision
        self.df.loc[mask, 'validated'] = bool(decision)

        if decision:
            self.status_var.set(f"Saved {point_id} as '{decision}'")
        else:
            self.status_var.set(f"Notes saved for {point_id} (no decision set)")

    def save_and_continue(self):
        self.save_notes()
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
        self.save_notes()
        self.save_csv()

        validated = self.df['validated'].sum()
        total = len(self.point_ids)
        messagebox.showinfo(
            "Saved",
            f"Validation saved to:\n{self.output_path}\n\n"
            f"Validated: {validated} / {total} points"
        )
        self.root.quit()

    def run(self):
        self.notes_text.focus_set()
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        self.root.mainloop()

    def on_closing(self):
        if messagebox.askyesno("Save?", "Save validation results before closing?"):
            self.save_notes()
            self.save_csv()
        self.root.destroy()
