# Changelog

All notable changes to `grassval` are documented here.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).
Versioning follows [Semantic Versioning](https://semver.org/).

## [Unreleased]

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
