"""Tests for the schema-safe DuckDB merge used by the cloud sync."""

from __future__ import annotations

import duckdb
import pytest

from arf.cloud_sync import SyncError, merge_duckdb


def _make_target(path):
    con = duckdb.connect(str(path))
    con.execute(
        "CREATE TABLE daily_prices ("
        "ticker VARCHAR, date DATE, close DOUBLE, turnover_rate DOUBLE, "
        "PRIMARY KEY (ticker, date))"
    )
    con.execute("INSERT INTO daily_prices VALUES ('A', '2026-01-01', 10.0, 1.0)")
    con.execute(
        "CREATE TABLE snapshot_revisions ("
        "ticker VARCHAR, as_of_date DATE, revision INTEGER, arf DOUBLE, "
        "PRIMARY KEY (ticker, as_of_date, revision))"
    )
    con.close()


def _make_source(path):
    con = duckdb.connect(str(path))
    # An older build: no turnover_rate column.
    con.execute(
        "CREATE TABLE daily_prices ("
        "ticker VARCHAR, date DATE, close DOUBLE, PRIMARY KEY (ticker, date))"
    )
    con.execute(
        "INSERT INTO daily_prices VALUES ('A', '2026-01-01', 99.0), ('B', '2026-01-02', 20.0)"
    )
    con.execute(
        "CREATE TABLE snapshot_revisions ("
        "ticker VARCHAR, as_of_date DATE, revision INTEGER, arf DOUBLE, "
        "PRIMARY KEY (ticker, as_of_date, revision))"
    )
    con.execute("INSERT INTO snapshot_revisions VALUES ('A', '2026-01-01', 1, 55.0)")
    con.close()


def test_merge_tolerates_schema_skew_and_is_idempotent(tmp_path):
    target = tmp_path / "target.db"
    source = tmp_path / "source.db"
    _make_target(target)
    _make_source(source)

    rows = merge_duckdb(source, target)
    assert rows["daily_prices"] == 1
    assert rows["snapshot_revisions"] == 1

    con = duckdb.connect(str(target), read_only=True)
    try:
        prices = con.execute(
            "SELECT ticker, close FROM daily_prices ORDER BY ticker"
        ).fetchall()
        # The existing row wins; the missing source ticker is added.
        assert prices == [("A", 10.0), ("B", 20.0)]
    finally:
        con.close()

    assert merge_duckdb(source, target) == {"daily_prices": 0, "snapshot_revisions": 0}


def test_merge_into_an_open_connection(tmp_path):
    target = tmp_path / "target.db"
    source = tmp_path / "source.db"
    _make_target(target)
    _make_source(source)

    con = duckdb.connect(str(target))
    try:
        rows = merge_duckdb(source, target, connection=con)
        assert rows["daily_prices"] == 1
    finally:
        con.close()


def test_missing_source_raises(tmp_path):
    with pytest.raises(SyncError):
        merge_duckdb(tmp_path / "missing.db", tmp_path / "target.db")
