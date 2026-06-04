# -*- mode: python ; coding: utf-8 -*-
#
# PyInstaller spec for siteval
#
# Usage:
#   pip install pyinstaller
#   pyinstaller siteval.spec
#
# Output: dist/siteval.exe  (Windows)  or  dist/siteval  (macOS/Linux)

import sys
from pathlib import Path

block_cipher = None

a = Analysis(
    [str(Path("src") / "siteval" / "app.py")],
    pathex=[str(Path("src"))],
    binaries=[],
    datas=[],
    hiddenimports=[
        # tkinter and its sub-modules are sometimes missed on certain builds
        "tkinter",
        "tkinter.ttk",
        "tkinter.filedialog",
        "tkinter.messagebox",
        # Pillow image format plugins
        "PIL._tkinter_finder",
        "PIL.Image",
        "PIL.ImageTk",
        "PIL.ImageDraw",
        "PIL.ImageFont",
        # pandas / numpy internals
        "pandas",
        "pandas._libs.tslibs.np_datetime",
        "pandas._libs.tslibs.nattype",
        "pandas._libs.tslibs.timedeltas",
        # siteval modules
        "siteval.app",
        "siteval.cli",
        "siteval.downloader",
        "siteval.validator",
        "siteval.params_ui",
        "siteval.utils",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name="siteval",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,          # no terminal window — GUI only
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    # icon="assets/siteval.ico",  # uncomment and add an .ico to enable
)
