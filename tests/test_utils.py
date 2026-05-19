"""Tests for grassval.utils — schema validation and CSV loading."""

import pytest
import pandas as pd
import tempfile
import os
from pathlib import Path

from grassval.utils import load_points, REQUIRED_COLUMNS


# ── fixtures ─────────────────────────────────────────────────────────────────

def _write_csv(tmp_path: Path, content: str) -> Path:
    p = tmp_path / "points.csv"
    p.write_text(content)
    return p


# ── load_points: happy path ───────────────────────────────────────────────────

def test_load_valid_csv(tmp_path):
    csv = _write_csv(tmp_path, "id,lat,lon,target_year\nSITE_001,39.1,-96.5,2022\n")
    df = load_points(csv)
    assert isinstance(df, pd.DataFrame)
    assert len(df) == 1
    assert list(df.columns[:4]) == ["id", "lat", "lon", "target_year"]


def test_load_csv_extra_columns_preserved(tmp_path):
    csv = _write_csv(tmp_path, "id,lat,lon,target_year,site\nA,1.0,2.0,2021,KONZ\n")
    df = load_points(csv)
    assert "site" in df.columns


def test_load_csv_string_path(tmp_path):
    csv = _write_csv(tmp_path, "id,lat,lon,target_year\nX,0.0,0.0,2020\n")
    df = load_points(str(csv))   # accepts str as well as Path
    assert len(df) == 1


def test_load_example_csv():
    here = Path(__file__).resolve().parent.parent
    example = here / "examples" / "points_example.csv"
    if not example.exists():
        pytest.skip("example CSV not found")
    df = load_points(example)
    assert len(df) == 5
    for col in REQUIRED_COLUMNS:
        assert col in df.columns


# ── load_points: error cases ──────────────────────────────────────────────────

def test_load_missing_file():
    with pytest.raises(FileNotFoundError, match="not found"):
        load_points("/nonexistent/path/points.csv")


def test_load_missing_required_column(tmp_path):
    csv = _write_csv(tmp_path, "id,lat,lon\nSITE_001,39.1,-96.5\n")  # no target_year
    with pytest.raises(ValueError, match="target_year"):
        load_points(csv)


def test_load_all_columns_missing(tmp_path):
    csv = _write_csv(tmp_path, "col_a,col_b\n1,2\n")
    with pytest.raises(ValueError):
        load_points(csv)


# ── REQUIRED_COLUMNS constant ─────────────────────────────────────────────────

def test_required_columns_contents():
    assert set(REQUIRED_COLUMNS) == {"id", "lat", "lon", "target_year"}


def test_required_columns_is_tuple():
    assert isinstance(REQUIRED_COLUMNS, tuple)


# ── custom required columns ───────────────────────────────────────────────────

def test_custom_required_columns_pass(tmp_path):
    csv = _write_csv(tmp_path, "plot_id,x,y\nP1,1.0,2.0\n")
    df = load_points(csv, required=["plot_id", "x", "y"])
    assert len(df) == 1


def test_custom_required_columns_fail(tmp_path):
    csv = _write_csv(tmp_path, "plot_id,x\nP1,1.0\n")
    with pytest.raises(ValueError, match="y"):
        load_points(csv, required=["plot_id", "x", "y"])
