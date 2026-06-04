"""Tests for siteval.utils — schema validation and CSV loading."""

import warnings
from pathlib import Path

import pandas as pd
import pytest

from siteval.utils import REQUIRED_COLUMNS, load_points


# ── helpers ───────────────────────────────────────────────────────────────────

def _write_csv(tmp_path: Path, content: str) -> Path:
    p = tmp_path / "points.csv"
    p.write_text(content)
    return p


# ── load_points: target_date column ──────────────────────────────────────────

def test_load_valid_csv_with_target_date(tmp_path):
    csv = _write_csv(tmp_path, "id,lat,lon,target_date\nSITE_001,39.1,-96.5,2022-06-15\n")
    df = load_points(csv)
    assert isinstance(df, pd.DataFrame)
    assert len(df) == 1
    assert "target_date" in df.columns


def test_target_date_parsed_as_date(tmp_path):
    import datetime
    csv = _write_csv(tmp_path, "id,lat,lon,target_date\nA,1.0,2.0,2021-03-01\n")
    df = load_points(csv)
    assert df["target_date"].iloc[0] == datetime.date(2021, 3, 1)


# ── load_points: target_year backward-compat ──────────────────────────────────

def test_load_valid_csv_with_target_year(tmp_path):
    csv = _write_csv(tmp_path, "id,lat,lon,target_year\nSITE_001,39.1,-96.5,2022\n")
    with warnings.catch_warnings(record=True) as w:
        warnings.simplefilter("always")
        df = load_points(csv)
        assert len(w) == 1
        assert "target_year" in str(w[0].message)
    assert "target_date" in df.columns


def test_target_year_converts_to_mid_year(tmp_path):
    import datetime
    csv = _write_csv(tmp_path, "id,lat,lon,target_year\nA,1.0,2.0,2020\n")
    with warnings.catch_warnings(record=True):
        warnings.simplefilter("always")
        df = load_points(csv)
    assert df["target_date"].iloc[0] == datetime.date(2020, 7, 1)


def test_target_date_takes_priority_over_year(tmp_path):
    import datetime
    csv = _write_csv(
        tmp_path,
        "id,lat,lon,target_date,target_year\nA,1.0,2.0,2021-01-15,2021\n",
    )
    df = load_points(csv)
    assert df["target_date"].iloc[0] == datetime.date(2021, 1, 15)


# ── load_points: extra columns and types ─────────────────────────────────────

def test_extra_columns_preserved(tmp_path):
    csv = _write_csv(
        tmp_path, "id,lat,lon,target_date,site\nA,1.0,2.0,2021-06-01,KONZ\n"
    )
    df = load_points(csv)
    assert "site" in df.columns


def test_load_csv_string_path(tmp_path):
    csv = _write_csv(tmp_path, "id,lat,lon,target_date\nX,0.0,0.0,2020-07-01\n")
    df = load_points(str(csv))
    assert len(df) == 1


def test_load_example_csv():
    here = Path(__file__).resolve().parent.parent
    example = here / "examples" / "points_example.csv"
    if not example.exists():
        pytest.skip("example CSV not found")
    with warnings.catch_warnings(record=True):
        warnings.simplefilter("always")
        df = load_points(example)
    assert len(df) == 5


# ── load_points: error cases ──────────────────────────────────────────────────

def test_load_missing_file():
    with pytest.raises(FileNotFoundError, match="not found"):
        load_points("/nonexistent/path/points.csv")


def test_load_missing_id_column(tmp_path):
    csv = _write_csv(tmp_path, "lat,lon,target_date\n39.1,-96.5,2022-01-01\n")
    with pytest.raises(ValueError, match="id"):
        load_points(csv)


def test_load_no_date_column(tmp_path):
    csv = _write_csv(tmp_path, "id,lat,lon\nA,1.0,2.0\n")
    with pytest.raises(ValueError, match="target_date"):
        load_points(csv)


def test_load_all_columns_missing(tmp_path):
    csv = _write_csv(tmp_path, "col_a,col_b\n1,2\n")
    with pytest.raises(ValueError):
        load_points(csv)


# ── REQUIRED_COLUMNS constant ─────────────────────────────────────────────────

def test_required_columns_contents():
    assert set(REQUIRED_COLUMNS) == {"id", "lat", "lon"}


def test_required_columns_is_tuple():
    assert isinstance(REQUIRED_COLUMNS, tuple)


# ── custom required columns ───────────────────────────────────────────────────

def test_custom_required_columns_pass(tmp_path):
    csv = _write_csv(tmp_path, "plot_id,x,y,target_date\nP1,1.0,2.0,2022-01-01\n")
    df = load_points(csv, required=["plot_id", "x", "y"])
    assert len(df) == 1


def test_custom_required_columns_fail(tmp_path):
    csv = _write_csv(tmp_path, "plot_id,x,target_date\nP1,1.0,2022-01-01\n")
    with pytest.raises(ValueError, match="y"):
        load_points(csv, required=["plot_id", "x", "y"])
