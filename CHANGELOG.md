# Changelog

All notable changes to `siteval` are documented here.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).
Versioning follows [Semantic Versioning](https://semver.org/).

## [Unreleased]

## [0.2.0] - 2026-06-02

### Added
- **Unified GUI app** (`siteval run`) — single-window 4-step workflow:
  CSV upload → parameter configuration → imagery download → validation.
- **Parameter UI** — configurable images per point (1–20), time span
  (1–50 yrs), zoom level (17/18/19), and tile grid size (1×1/3×3/5×5).
  Live interval label shows computed gap between images as you adjust sliders.
- **Temporal sampling** — N evenly-spaced snapshots centred on the target
  date, capped to the Wayback archive window. Closest available capture is
  selected for each interval.
- **Spatial scale control** — `tile_size` parameter (1, 3, or 5) controls
  the downloaded tile grid: 256 px / 768 px / 1280 px output per image.
- **Caution decision** — validator now supports three states: Accept (A),
  Reject (R), Caution (C). Decision buttons are color-coded green/red/amber.
- **Dual CSV schema** — accepts `target_date` (YYYY-MM-DD) or legacy
  `target_year` (integer, auto-converted to YYYY-07-01 with a warning).
- `siteval download` flags: `--n-images`, `--span-years`, `--tile-size`.
- PyInstaller spec (`siteval.spec`) and `build.py` for producing a
  standalone `.exe` / app bundle.

### Changed
- Package renamed from `grassval` to `siteval` (domain-agnostic).
- `WaybackDownloader.find_unique_layers` replaced by
  `find_layers_for_point(target_date, lat, lon)` with new temporal logic.
- Validator resumes from first *unvalidated* point on relaunch (previously
  first point always).
- Image labels now show the capture date only (no "Image N:" prefix).
- `REQUIRED_COLUMNS` tightened to `(id, lat, lon)` — date column is
  handled separately to support both schema variants.

### Removed
- Hardcoded four-snapshot strategy (target / before / after / recent)
  replaced by the configurable evenly-spaced approach.

## [0.1.0] - 2026-05-19

### Added
- `WaybackDownloader` — fetches up to four visually unique Esri Wayback
  snapshots per point using perceptual hashing to deduplicate identical tiles.
- `ImageValidator` — Tk GUI for binary Accept/Reject validation with keyboard
  shortcuts (A/R/Enter/arrows), auto-save on close, and resume on relaunch.
- `load_points` utility — validates required CSV schema (`id`, `lat`, `lon`,
  `target_year`) in one call, shared by downloader and validator.
- `grassval download` CLI subcommand with `--csv`, `--output`, `--zoom`,
  `--logs`, `--verbose` flags.
- `grassval validate` CLI subcommand with `--csv`, `--imagery`, `--output`,
  `--filename` flags.
- MIT license.
- `examples/filter_neon.py` — end-to-end example of filtering the NEON VST
  non-forest reference CSV into a `grassval`-compatible `points.csv`.
- `examples/points_example.csv` — five-row example input CSV.
