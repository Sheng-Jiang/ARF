"""End-to-end pipeline integration test."""
from datetime import date

import pandas as pd
import pytest

from arf.run import run_pipeline


@pytest.mark.integration
class TestPipelineE2E:
    @pytest.fixture(scope="class")
    def run_output(self, tmp_path_factory):
        base = tmp_path_factory.mktemp("pipeline")
        as_of = date(2026, 5, 28)
        run_pipeline(as_of=as_of, data_dir=base / "data", report_dir=base / "reports")
        return base, as_of

    def test_produces_parquet(self, run_output):
        base, as_of = run_output
        parquet = base / "data" / "snapshots" / f"arf_{as_of}.parquet"
        assert parquet.exists(), f"Parquet file not found: {parquet}"

    def test_produces_markdown_report(self, run_output):
        base, as_of = run_output
        md = base / "reports" / f"arf_{as_of}.md"
        assert md.exists(), f"Markdown report not found: {md}"
        content = md.read_text()
        assert "US Leg" in content or "## US" in content
        assert "China Leg" in content or "## China" in content
        assert "Pre-IPO" in content

    def test_produces_thermometer_html(self, run_output):
        base, _ = run_output
        html = base / "reports" / "thermometer.html"
        assert html.exists(), "thermometer.html not found"
        assert "plotly" in html.read_text().lower()

    def test_parquet_has_expected_columns(self, run_output):
        base, as_of = run_output
        df = pd.read_parquet(base / "data" / "snapshots" / f"arf_{as_of}.parquet")
        for col in ("ticker", "arf", "e_score", "v_score", "decile", "froth_flag", "leg"):
            assert col in df.columns, f"Parquet missing column: {col}"

    def test_idempotent_rerun(self, run_output, tmp_path_factory):
        base, as_of = run_output
        base2 = tmp_path_factory.mktemp("pipeline2")
        run_pipeline(as_of=as_of, data_dir=base2 / "data", report_dir=base2 / "reports")
        df1 = pd.read_parquet(base / "data" / "snapshots" / f"arf_{as_of}.parquet")
        df2 = pd.read_parquet(base2 / "data" / "snapshots" / f"arf_{as_of}.parquet")
        assert set(df1["ticker"]) == set(df2["ticker"])

    def test_partial_failure_continues(self, tmp_path_factory, monkeypatch):
        """A single fetcher throwing should not abort the whole run."""
        from arf.fetchers import us as us_mod

        original = us_mod.fetch_us

        call_count = {"n": 0}

        def flaky_fetch(entry, as_of):
            call_count["n"] += 1
            if call_count["n"] == 1:
                raise RuntimeError("simulated network error")
            return original(entry, as_of)

        monkeypatch.setattr(us_mod, "fetch_us", flaky_fetch)

        base = tmp_path_factory.mktemp("partial")
        as_of = date(2026, 5, 28)
        run_pipeline(as_of=as_of, data_dir=base / "data", report_dir=base / "reports")
        parquet = base / "data" / "snapshots" / f"arf_{as_of}.parquet"
        assert parquet.exists()
        df = pd.read_parquet(parquet)
        assert len(df) > 0
