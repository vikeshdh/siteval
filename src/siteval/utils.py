"""Shared helpers for siteval.

Centralises the CSV schema and the loader used by the CLI, downloader, and
validator. Accepts either ``target_date`` (YYYY-MM-DD) or ``target_year``
(integer) — if the latter is detected it is converted to YYYY-07-01 with a
one-line warning so existing CSVs keep working.
"""

from __future__ import annotations

import warnings
from pathlib import Path
from typing import Iterable

import pandas as pd

REQUIRED_COLUMNS: tuple[str, ...] = ("id", "lat", "lon")
_DATE_COLUMN = "target_date"
_YEAR_COLUMN = "target_year"


def load_points(
    csv_path: str | Path,
    required: Iterable[str] = REQUIRED_COLUMNS,
) -> pd.DataFrame:
    """Read a points CSV, validate schema, and normalise the date column.

    Accepts either ``target_date`` (YYYY-MM-DD string) or ``target_year``
    (integer). If only ``target_year`` is present it is converted to
    ``YYYY-07-01`` and a warning is emitted.

    Parameters
    ----------
    csv_path:
        Path to the input CSV.
    required:
        Columns that must be present (default: id, lat, lon).

    Returns
    -------
    pandas.DataFrame
        Frame with a ``target_date`` column of ``datetime.date`` objects.

    Raises
    ------
    FileNotFoundError
        If ``csv_path`` does not exist.
    ValueError
        If required columns are missing or neither date column is present.
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

    has_date = _DATE_COLUMN in df.columns
    has_year = _YEAR_COLUMN in df.columns

    if not has_date and not has_year:
        raise ValueError(
            f"CSV must have either '{_DATE_COLUMN}' (YYYY-MM-DD) or "
            f"'{_YEAR_COLUMN}' (integer) column."
        )

    if not has_date and has_year:
        warnings.warn(
            f"'{_YEAR_COLUMN}' column detected — converting to '{_DATE_COLUMN}' "
            f"using mid-year (YYYY-07-01). Add a '{_DATE_COLUMN}' column for "
            "full date precision.",
            UserWarning,
            stacklevel=2,
        )
        df[_DATE_COLUMN] = df[_YEAR_COLUMN].apply(lambda y: f"{int(y):04d}-07-01")

    df[_DATE_COLUMN] = pd.to_datetime(df[_DATE_COLUMN]).dt.date

    return df
