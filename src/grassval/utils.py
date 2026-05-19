"""Shared helpers for grassval.

Centralises the CSV schema (`REQUIRED_COLUMNS`) and the loader that the CLI,
the downloader, and the validator all use to read input. Keeping schema
checks in one place is what makes grassval dataset-agnostic — any CSV that
satisfies the schema works.
"""

from __future__ import annotations

from pathlib import Path
from typing import Iterable

import pandas as pd

# Required columns for every grassval input CSV.
REQUIRED_COLUMNS: tuple[str, ...] = ("id", "lat", "lon", "target_year")


def load_points(csv_path: str | Path,
                required: Iterable[str] = REQUIRED_COLUMNS) -> pd.DataFrame:
    """Read a points CSV and verify it has the required columns.

    Parameters
    ----------
    csv_path : str | Path
        Path to the input CSV.
    required : iterable of str, optional
        Columns that must be present. Defaults to ``REQUIRED_COLUMNS``.

    Returns
    -------
    pandas.DataFrame
        The loaded frame.

    Raises
    ------
    FileNotFoundError
        If `csv_path` does not exist.
    ValueError
        If any required column is missing.
    """
    path = Path(csv_path)
    if not path.exists():
        raise FileNotFoundError(f"CSV file not found: {path}")

    df = pd.read_csv(path)
    missing = set(required) - set(df.columns)
    if missing:
        raise ValueError(
            f"CSV is missing required columns: {sorted(missing)}. "
            f"Required: {list(required)}"
        )
    return df
