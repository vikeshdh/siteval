"""Build script: produces dist/siteval.exe (or dist/siteval on macOS/Linux).

Usage:
    python build.py

Requires PyInstaller:
    pip install pyinstaller
"""

import subprocess
import sys


def main():
    try:
        import PyInstaller  # noqa: F401
    except ImportError:
        print("PyInstaller not found. Install it with:  pip install pyinstaller")
        sys.exit(1)

    result = subprocess.run(
        [sys.executable, "-m", "PyInstaller", "siteval.spec", "--clean"],
        check=False,
    )

    if result.returncode == 0:
        print("\nBuild succeeded.")
        print("  Executable: dist/siteval.exe  (Windows)")
        print("  Executable: dist/siteval       (macOS / Linux)")
    else:
        print("\nBuild failed — check the output above for details.")
        sys.exit(result.returncode)


if __name__ == "__main__":
    main()
