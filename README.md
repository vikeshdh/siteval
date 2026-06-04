# siteval

[![CI](https://github.com/vikeshdh/siteval/actions/workflows/ci.yml/badge.svg)](https://github.com/vikeshdh/siteval/actions/workflows/ci.yml)
[![PyPI version](https://badge.fury.io/py/siteval.svg)](https://pypi.org/project/siteval/)
[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

**siteval** downloads [Esri Wayback](https://livingatlas.arcgis.com/wayback/)
very-high-resolution historical imagery for a list of geographic points and
presents them in a clean **Accept / Reject / Caution** GUI for visual
validation. Give it a CSV of coordinates and a target date; it samples imagery
through time around each point so you can review land-cover change and confirm
what's on the ground.

It is **dataset-agnostic** — any CSV with `id`, `lat`, `lon`, and a
`target_date` (or `target_year`) column works.

**Use cases:** land-cover validation, training-data quality control, plot-level
habitat assessment, change-detection review, or any remote sensing workflow
where a human needs to judge historical satellite/aerial imagery.

---

## Two ways to use it

| | Best for |
|---|---|
| **Desktop app** (`siteval run`) | A guided 4-step window: upload → set parameters → download → validate. No command line needed. |
| **Command line** (`siteval download` / `siteval validate`) | Scripting, batch jobs, and reproducible pipelines. |

---

## Installation

```bash
pip install siteval
```

Or from source:

```bash
git clone https://github.com/vikeshdh/siteval.git
cd siteval
pip install -e ".[dev]"
```

Requires Python 3.9+. Dependencies: `pandas`, `requests`, `tqdm`, `Pillow`.
`tkinter` powers the GUI and ships with most Python distributions
(on Linux: `sudo apt-get install python3-tk`).

### Standalone executable (no Python required)

To build a double-clickable app for sharing with non-technical users:

```bash
pip install pyinstaller
python build_exe.py
```

This produces `dist/siteval.exe` (Windows) or `dist/siteval` (macOS/Linux).

---

## Quickstart — desktop app

```bash
siteval run
```

A single window walks you through four steps:

1. **Upload CSV** — pick your points file; siteval previews it and checks the schema.
2. **Parameters** — set how far back/forward in time to sample, the interval
   between images, the zoom level, and the tile-grid size. A live preview shows
   exactly how many images each point will produce.
3. **Download** — imagery is fetched from Esri Wayback with a progress bar.
4. **Validate** — review each point and record Accept / Reject / Caution + notes.

---

## Quickstart — command line

### 1. Prepare a CSV

`siteval` requires these columns:

| Column        | Type   | Description                                              |
|---------------|--------|----------------------------------------------------------|
| `id`          | string | Unique point identifier (used as folder/filename prefix) |
| `lat`         | float  | Decimal latitude, WGS84                                  |
| `lon`         | float  | Decimal longitude, WGS84                                 |
| `target_date` | date   | Target acquisition date, `YYYY-MM-DD`                    |

`target_year` (integer) is also accepted for backward compatibility — it is
converted to mid-year (`YYYY-07-01`) automatically. Extra columns pass through
to the output unchanged.

```csv
id,lat,lon,target_date
KONZ_001,39.1008,-96.5631,2020-07-15
WOOD_002,47.1282,-99.2413,2019-06-01
```

See [`examples/test_points.csv`](examples/test_points.csv) for a ready-to-use
sample.

### 2. Download imagery

```bash
siteval download --csv points.csv --output imagery/ \
  --back 1 --back-unit years \
  --forward 1 --forward-unit years \
  --interval 1 --interval-unit years
```

For each point, siteval samples Esri Wayback captures at a fixed **interval**
across a window that extends a given distance **back** and **forward** from the
target date, then picks the closest available capture to each step. Perceptual
hashing skips visually identical captures. Images are written as
`imagery/<id>/<id>_<N>_<YYYY-MM-DD>.png`.

The example above produces three images per point: one year before, the target
date, and one year after.

### 3. Validate

```bash
siteval validate --csv points.csv --imagery imagery/ --output results/
```

A GUI opens showing each point's images side by side, with the capture date on
every image. For each point:

| Key | Action |
|-----|--------|
| `A` | Mark as **Accept** |
| `R` | Mark as **Reject** |
| `C` | Mark as **Caution** |
| `Enter` / `Ctrl+S` | Save and advance |
| `←` / `→` | Navigate to previous / next point |

Decisions auto-save to `results/validated_points.csv` on exit. The validator
resumes from the first unvalidated point if you close and reopen.

---

## Python API

```python
from siteval import WaybackDownloader, ImageValidator

# Download imagery for all points in a CSV
downloader = WaybackDownloader(
    output_dir="imagery",
    zoom=18,
    back_days=365, forward_days=365, interval_days=365,  # 1 yr each side, yearly
    tile_size=3,
)
stats = downloader.process_csv("points.csv")
print(f"Downloaded {stats['success']} / {stats['total']} points")

# Launch the validation GUI
validator = ImageValidator(
    input_dir="imagery",
    csv_path="points.csv",
    output_path="results/validated_points.csv",
)
validator.run()
```

```python
# Validate the CSV schema before processing
from siteval import load_points, REQUIRED_COLUMNS

df = load_points("my_points.csv")   # raises FileNotFoundError or ValueError if invalid
```

---

## CLI reference

```
siteval run

siteval download  --csv PATH --output DIR
                  [--back N --back-unit days|months|years]
                  [--forward N --forward-unit days|months|years]
                  [--interval N --interval-unit days|months|years]
                  [--zoom 17|18|19] [--tile-size 1|3|5]
                  [--logs DIR] [--verbose]

siteval validate  --csv PATH --imagery DIR --output DIR [--filename NAME]
```

```
siteval download --help
siteval validate --help
```

---

## Parameters explained

| Parameter | What it controls |
|-----------|------------------|
| **back / forward** | How far before and after the target date to sample (e.g. 2 years back, 0 forward). |
| **interval** | The step between sampled images (e.g. every 6 months). The number of images is derived from the window ÷ interval. |
| **zoom** | Wayback tile zoom: `17` (~1.2 km view), `18` (~600 m), `19` (~300 m). |
| **tile-size** | Grid of tiles per image: `1×1` (256 px), `3×3` (768 px), `5×5` (1280 px). Larger = more surrounding context. |

---

## Output format

`validated_points.csv` contains all original columns plus:

| Column      | Values                                   |
|-------------|------------------------------------------|
| `decision`  | `accept`, `reject`, `caution`, or `""`   |
| `validated` | `True` / `False`                         |
| `notes`     | Free-text notes from the GUI             |

---

## Examples

- [`examples/test_points.csv`](examples/test_points.csv) — 10 sample points
  spanning varied land-cover types, using the `target_date` schema.
- [`examples/filter_neon.py`](examples/filter_neon.py) — filters the NEON VST
  non-forest reference CSV into a siteval-compatible `points.csv`. Runs in
  Google Colab or locally.

```bash
python examples/filter_neon.py
```

---

## Development

```bash
pip install -e ".[dev]"
pytest tests/ -v
```

Contributions welcome. Please open an issue before submitting a PR.

---

## Citation

If you use `siteval` in published research, please cite:

```
Dheeriya, V. (2026). siteval: A Python toolkit for Esri Wayback imagery
download and visual validation of geographic points.
https://github.com/vikeshdh/siteval
```

---

## License

MIT — see [LICENSE](LICENSE).
