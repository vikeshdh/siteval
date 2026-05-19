#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""filter_neon_for_validation.py

Standalone (Google Colab compatible) script that:
1. Mounts Google Drive
2. Reads `NEON_vst_nonforest_reference.csv` from your Drive
3. Filters to grassland plots (2016-2025, tree_flag == 'no')
4. Deduplicates by plotID, keeping the most recent year per plot
5. Keeps EVERY plot that passes the filter (no random sampling)
6. Exports `points.csv` to ValidationProgram_total/data/ on Drive

Output columns: id, lat, lon, target_year   (id = siteID_plotID)

Before running on Colab: upload `NEON_vst_nonforest_reference.csv` to your
Google Drive at the root of `My Drive`.
"""

# ── Step 1 — Mount Google Drive (Colab only) ────────────────────────────
try:
    from google.colab import drive
    drive.mount('/content/drive')
    print('Google Drive mounted at /content/drive')
    DRIVE_ROOT = '/content/drive/My Drive'
except ImportError:
    # Running outside Colab — assume paths are already accessible
    DRIVE_ROOT = '.'
    print('Not running in Colab — using local paths')

# ── Step 2 — Set file paths ─────────────────────────────────────────────
import os

INPUT_CSV  = os.path.join(DRIVE_ROOT, 'NEON_vst_nonforest_reference.csv')
OUTPUT_CSV = os.path.join(DRIVE_ROOT, 'ValidationProgram_total', 'data',
                          'points.csv')

YEAR_MIN = 2016   # earliest year with Sentinel-1/2 coverage
YEAR_MAX = 2025   # latest year

os.makedirs(os.path.dirname(OUTPUT_CSV), exist_ok=True)

if not os.path.exists(INPUT_CSV):
    raise FileNotFoundError(
        f'Could not find: {INPUT_CSV}\n'
        f'Check that the file is uploaded to Google Drive and the path '
        f'above is correct.'
    )
print('Input file found ✓')

# ── Step 3 — Filter ─────────────────────────────────────────────────────
import pandas as pd

print(f'Reading: {INPUT_CSV}')
df = pd.read_csv(INPUT_CSV)
print(f'Loaded {len(df):,} rows')

# sampleID format: HBP.HARV0240048.20130724
# The date is the final 8 digits: YYYYMMDD — extract the YYYY
df['year'] = (
    df['sampleID']
    .str.extract(r'\.(\d{4})\d{4}$')
    .astype(float)
)

mask = (
    (df['year'] >= YEAR_MIN) &
    (df['year'] <= YEAR_MAX) &
    (df['tree_flag'] == 'no')
)
filtered = df[mask].copy()
print(f'\nAfter filtering ({YEAR_MIN}-{YEAR_MAX}, tree_flag=no):')
print(f'  {len(filtered):,} rows  |  {filtered["siteID"].nunique()} sites')

# ── Step 4 — Deduplicate by plotID (keep most recent year) ──────────────
unique_plots = (
    filtered
    .sort_values('year', ascending=False)
    .drop_duplicates(subset='plotID')
    [['siteID', 'plotID', 'decimalLatitude', 'decimalLongitude', 'year']]
    .reset_index(drop=True)
)
print(f'  {len(unique_plots)} unique grassland plots after dedup')

# ── Step 5 — Build output frame (no sampling — keep all plots) ──────────
out = unique_plots.rename(columns={
    'decimalLatitude':  'lat',
    'decimalLongitude': 'lon',
    'year':             'target_year',
})
out['id']          = out['siteID'] + '_' + out['plotID']
out['target_year'] = out['target_year'].astype(int)
out = out[['id', 'lat', 'lon', 'target_year']]

# ── Step 6 — Summary ────────────────────────────────────────────────────
per_site = (
    unique_plots.groupby('siteID').size().rename('plot_count')
    .sort_values(ascending=False)
)

print('\n' + '=' * 50)
print('Summary')
print('=' * 50)
print(f'Total plots:   {len(out)}')
print(f'Unique sites:  {out["id"].str.split("_").str[0].nunique()}')
print('\nPer-site plot counts:')
print(per_site.to_string())

# ── Step 7 — Export ─────────────────────────────────────────────────────
out.to_csv(OUTPUT_CSV, index=False)
print(f'\nSaved {len(out)} rows to: {OUTPUT_CSV}')
