"""Storage abstraction: DATA_SOURCE=local reads data/arf.db, DATA_SOURCE=gcs downloads from GCS."""
import os
import tempfile
from datetime import date
from pathlib import Path

import duckdb
import pandas as pd
import streamlit as st

DATA_SOURCE = os.getenv("DATA_SOURCE", "local")
LOCAL_DB_PATH = Path(os.getenv("LOCAL_DB_PATH", "data/arf.db"))
GCS_BUCKET = os.getenv("GCS_BUCKET", "")
GCS_DB_OBJECT = os.getenv("GCS_DB_OBJECT", "arf.db")


@st.cache_resource(ttl=3600)
def _open_conn() -> duckdb.DuckDBPyConnection:
    if DATA_SOURCE == "gcs":
        from google.cloud import storage  # type: ignore[import]
        client = storage.Client()
        tmp_path = Path(tempfile.mkdtemp()) / "arf.db"
        client.bucket(GCS_BUCKET).blob(GCS_DB_OBJECT).download_to_filename(str(tmp_path))
        return duckdb.connect(str(tmp_path), read_only=True)
    return duckdb.connect(str(LOCAL_DB_PATH), read_only=True)


def list_dates() -> list[date]:
    rows = _open_conn().execute(
        "SELECT DISTINCT as_of_date FROM snapshots ORDER BY as_of_date DESC"
    ).fetchall()
    return [r[0] for r in rows]


def load_snapshot(as_of: date) -> pd.DataFrame:
    return _open_conn().execute(
        "SELECT * FROM snapshots WHERE as_of_date = ?", [as_of]
    ).fetchdf()


def load_thermometer_series() -> pd.DataFrame:
    return _open_conn().execute("""
        SELECT
            as_of_date,
            leg,
            COUNT(*) FILTER (WHERE arf >= 90)       AS count_arf_gte_90,
            COUNT(*) FILTER (WHERE froth_flag = TRUE) AS count_froth,
            MEDIAN(arf)                              AS median_arf,
            COUNT(*)                                 AS total
        FROM snapshots
        GROUP BY as_of_date, leg
        ORDER BY as_of_date, leg
    """).fetchdf()


def refresh_data() -> None:
    _open_conn.clear()
