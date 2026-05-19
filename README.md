# grassval

[![CI](https://github.com/vikeshdh/grassval/actions/workflows/ci.yml/badge.svg)](https://github.com/vikeshdh/grassval/actions/workflows/ci.yml)
[![PyPI version](https://badge.fury.io/py/grassval.svg)](https://pypi.org/project/grassval/)
[![Python 3.9+](https://img.shields.io/badge/python-3.9+-blue.svg)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

**grassval** downloads Esri Wayback very-high-resolution imagery for a list of
geographic points and presents them in a binary Accept/Reject GUI for visual
validation. It was built for the NEON grassland validation pipeline at UCSB but
contains no dataset-specific logic — any CSV with `id`, `lat`, `lon`,
`target_year` columns works.

**Use cases:** land-cover validation, training-data quality control, plot-level
habitat assessment, change detection review, or any remote sensing workflow
where a human needs to make a binary judgment on historical satellite/aerial
imagery.

---

## Installation

```bash
pip install grassval
```

Or from source:

```bash
git clone https://github.com/vikeshdh/grassval.git
cd grassval
pip install -e ".[dev]"
```

Requires Python 3.9+. Dependencies: `pandas`, `requests`, `tqdm`, `Pillow`.
`tkinter` is required for the GUI and is included with most Python distributions
(on Linux: `sudo apt-get install python3-tk`).

---

## Quickstart

### 1. Prepare a CSV

`grassval` requires a CSV with exactly these columns:

| Column        | Type   | Description                                      |
|---------------|--------|--------------------------------------------------|
| `id`          | string | Unique point identifier (used as folder/filename prefix) |
| `lat`         | float  | Decimal latitude, WGS84                          |
| `lon`         | float  | Decimal longitude, WGS84                         |
| `target_year` | int    | Target acquisition year (e.g. `2022`)            |

Extra columns are passed through to the output unchanged.

```csv
id,lat,lon,target_year
KONZ_001,39.1008,-96.5631,2022
WOOD_012,47.1282,-99.2413,2021
```

See [`examples/points_example.csv`](examples/points_example.csv) for a
ready-to-use sample.

### 2. Download imagery

```bash
grassval download --csv points.csv --output imagery/
```

For each point, grassval fetches up to **four visually unique** Wayback
snapshots — target year, one before, one after, and the most recent — at
zoom 18. Perceptual hashing is used to skip duplicates. Images are written as
`imagery/<id>/<id>_<N>_<YYYY-MM-DD>.png`.

### 3. Validate

```bash
grassval validate --csv points.csv --imagery imagery/ --output results/
```

A GUI opens showing the downloaded images side by side. For each point:

| Key | Action |
|-----|--------|
| `A` | Mark as **Accept** |
| `R` | Mark as **Reject** |
| `Enter` / `Ctrl+S` | Save and advance |
| `←` / `→` | Navigate to previous / next point |

Decisions auto-save to `results/validated_points.csv` on exit. The validator
resumes from where you left off if you close and reopen.

---

## Python API

```python
from grassval import WaybackDownloader, ImageValidator

# Download imagery for all points in a CSV
downloader = WaybackDownloader(output_dir="imagery", zoom=18)
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
from grassval import load_points, REQUIRED_COLUMNS

df = load_points("my_points.csv")   # raises FileNotFoundError or ValueError if invalid
```

---

## CLI reference

```
grassval download  --csv PATH --output DIR [--zoom 17|18|19] [--logs DIR] [--verbose]
grassval validate  --csv PATH --imagery DIR --output DIR [--filename NAME]
```

```
grassval download --help
grassval validate --help
```

---

## Output format

`validated_points.csv` contains all original columns plus:

| Column      | Values                        |
|-------------|-------------------------------|
| `decision`  | `accept`, `reject`, or `""`   |
| `validated` | `True` / `False`              |
| `notes`     | Free-text notes from the GUI  |

---

## Examples

`examples/filter_neon.py` — filters the NEON VST non-forest reference CSV
(tree_flag == "no", 2016–2025) into a `grassval`-compatible `points.csv`. Runs
in Google Colab or locally.

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

If you use `grassval` in published research, please cite:

```
Dheeriya, V. (2026). grassval: A Python toolkit for Wayback imagery download
and visual validation of remote sensing points.
https://github.com/vikeshdh/grassval
```

---

## License

MIT — see [LICENSE](LICENSE).
