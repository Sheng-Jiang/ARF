from datetime import date

import pandas as pd
import pytest

from arf.reporting import render_markdown, render_thermometer_html


def _make_report_df() -> pd.DataFrame:
    """Minimal scored DataFrame covering US, China, Pre-IPO and Europe-ref legs."""
    us = [
        {"ticker": "NVDA", "name": "NVIDIA", "leg": "US", "layer": "L2",
         "arf": 75.0, "decile": 2, "e_score": 90.0, "v_score": 62.0, "froth_flag": False,
         "forward_pe": 23.0, "ps_ratio": 21.0, "revenue_yoy_growth": 0.65, "roe": 1.14,
         "policy_premium": False},
        {"ticker": "PLTR", "name": "Palantir", "leg": "US", "layer": "L5",
         "arf": 98.0, "decile": 1, "e_score": 95.0, "v_score": 95.0, "froth_flag": True,
         "forward_pe": 90.0, "ps_ratio": 80.0, "revenue_yoy_growth": 0.68, "roe": 0.33,
         "policy_premium": False},
        {"ticker": "CSCO", "name": "Cisco", "leg": "US", "layer": "L3",
         "arf": 15.0, "decile": 9, "e_score": 15.0, "v_score": 20.0, "froth_flag": False,
         "forward_pe": 18.0, "ps_ratio": 5.0, "revenue_yoy_growth": 0.06, "roe": 0.35,
         "policy_premium": False},
    ]
    china = [
        {"ticker": "688256.SH", "name": "寒武纪 Cambricon", "leg": "China", "layer": "L2",
         "arf": 96.0, "decile": 1, "e_score": 92.0, "v_score": 98.0, "froth_flag": True,
         "forward_pe": 273.0, "ps_ratio": 50.0, "revenue_yoy_growth": 23.86, "roe": 0.02,
         "policy_premium": True},
    ]
    preipo = [
        {"ticker": "ANTHROPIC", "name": "Anthropic", "leg": "Pre-IPO", "layer": "L4",
         "arf": None, "decile": None, "e_score": None, "v_score": None, "froth_flag": None,
         "forward_pe": None, "ps_ratio": None, "revenue_yoy_growth": None, "roe": None,
         "policy_premium": False},
    ]
    europe = [
        {"ticker": "ASML", "name": "ASML", "leg": "Europe-ref", "layer": "L2",
         "arf": None, "decile": None, "e_score": None, "v_score": None, "froth_flag": None,
         "forward_pe": 43.0, "ps_ratio": 16.0, "revenue_yoy_growth": 0.31, "roe": 0.50,
         "policy_premium": False},
    ]
    return pd.DataFrame(us + china + preipo + europe)


class TestRenderMarkdown:
    @pytest.fixture(scope="class")
    def report(self):
        df = _make_report_df()
        return render_markdown(df, as_of=date(2026, 5, 28))

    def test_contains_us_leg_section(self, report):
        assert "US Leg" in report or "## US" in report

    def test_contains_china_leg_section(self, report):
        assert "China Leg" in report or "## China" in report

    def test_contains_preipo_table(self, report):
        assert "Pre-IPO" in report

    def test_contains_europe_reference_table(self, report):
        assert "Europe" in report

    def test_contains_as_of_date(self, report):
        assert "2026-05-28" in report

    def test_us_leg_contains_nvda(self, report):
        assert "NVDA" in report

    def test_china_leg_contains_cambricon(self, report):
        assert "688256" in report or "Cambricon" in report

    def test_froth_flag_marked_distinctly(self, report):
        # PLTR and Cambricon are froth-flagged; must have some visual marker
        assert "froth" in report.lower() or "★" in report or "⚠" in report or "**True**" in report

    def test_thermometer_summary_present(self, report):
        assert "D1" in report or "froth" in report.lower() or "top decile" in report.lower()

    def test_pltr_froth_flagged_in_report(self, report):
        # PLTR row is in the US section with froth_flag=True
        pltr_line_idx = report.find("PLTR")
        assert pltr_line_idx >= 0
        # Somewhere near the PLTR row there should be the froth marker
        context = report[max(0, pltr_line_idx - 5): pltr_line_idx + 200]
        assert "True" in context or "★" in context or "froth" in context.lower()

    def test_csco_low_decile_shown(self, report):
        assert "CSCO" in report

    def test_report_is_markdown(self, report):
        assert report.startswith("#") or "##" in report


class TestRenderThermometerHtml:
    def test_returns_string(self):
        result = render_thermometer_html(pd.DataFrame(columns=["as_of_date", "leg",
                                                                "count_arf_gte_90",
                                                                "count_froth", "median_arf"]))
        assert isinstance(result, str)

    def test_contains_plotly_script(self):
        result = render_thermometer_html(pd.DataFrame(columns=["as_of_date", "leg",
                                                                "count_arf_gte_90",
                                                                "count_froth", "median_arf"]))
        assert "plotly" in result.lower() or "<html" in result.lower()

    def test_with_data_contains_traces(self):
        thermo = pd.DataFrame([
            {"as_of_date": date(2026, 5, 21), "leg": "US",
             "count_arf_gte_90": 3, "count_froth": 2, "median_arf": 55.0},
            {"as_of_date": date(2026, 5, 28), "leg": "US",
             "count_arf_gte_90": 4, "count_froth": 3, "median_arf": 58.0},
        ])
        result = render_thermometer_html(thermo)
        assert "plotly" in result.lower() or "Plotly" in result
