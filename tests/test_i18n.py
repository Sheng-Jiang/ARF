"""Tests for the webapp language helpers (webapp/ui.py)."""

from streamlit.testing.v1 import AppTest

_APP = """
import streamlit as st

from webapp.ui import get_current_lang, set_current_lang, tr

st.write("lang=" + get_current_lang())
st.write("tr=" + tr("中文", "English"))

if st.button("switch-zh"):
    set_current_lang("zh")
    st.rerun()
"""


def _run() -> AppTest:
    at = AppTest.from_string(_APP, default_timeout=30)
    at.run()
    return at


def test_defaults_to_english():
    at = _run()

    assert at.markdown[0].value == "lang=en"
    assert at.markdown[1].value == "tr=English"


def test_query_param_deep_link_is_honoured():
    at = _run()
    at.query_params["lang"] = "zh"
    at.run()

    assert at.markdown[0].value == "lang=zh"
    assert at.markdown[1].value == "tr=中文"


def test_switcher_updates_language():
    at = _run()
    at.button[0].click().run()

    assert at.markdown[0].value == "lang=zh"
    assert at.markdown[1].value == "tr=中文"


def test_no_legacy_pages_directory_and_views_exist():
    """Streamlit _mpa_v1 hijacks st.navigation whenever webapp/pages/ exists."""
    from pathlib import Path

    from webapp.app import _PAGES

    assert not Path("webapp/pages").exists()
    for _, specs in _PAGES.values():
        for spec in specs:
            assert Path("webapp", spec["path"]).is_file(), f"Missing view: {spec['path']}"


def test_app_navigation_preserves_switcher_across_views():
    from streamlit.util import calc_hash

    at = AppTest.from_file("webapp/app.py", default_timeout=30)
    for slug in ("valuation-leaderboard", "bubble-thermometer", "dual-value-chain", "ai-screener", "research-note"):
        at._page_hash = calc_hash(slug)
        at.run()
        assert not at.exception
        radios = [r.label for r in at.sidebar.radio]
        assert any("Language" in label for label in radios), f"Missing language switcher on {slug}"


def test_jobs_status_messages_respect_lang(monkeypatch):
    from types import SimpleNamespace

    from webapp import jobs

    monkeypatch.setenv("GCP_PROJECT", "demo-project")

    class _FakeExecutionsClient:
        def get_execution(self, name: str):
            return SimpleNamespace(
                conditions=[SimpleNamespace(type="Succeeded", status="True")],
                cancelled=False,
            )

    monkeypatch.setattr("google.cloud.run_v2.ExecutionsClient", _FakeExecutionsClient)
    res_en = jobs.get_execution_status("exec-1", lang="en")
    res_zh = jobs.get_execution_status("exec-1", lang="zh")
    assert res_en["message"] == "Run succeeded ✓"
    assert res_zh["message"] == "运行成功 ✓"


def test_kline_chart_respects_lang():
    import pandas as pd

    from webapp.charts import draw_pro_kline

    df = pd.DataFrame({
        "date": ["2026-10-01", "2026-10-02"],
        "open": [100.0, 101.0],
        "close": [101.0, 102.0],
        "low": [99.0, 100.0],
        "high": [102.0, 103.0],
        "volume": [1000, 1100],
    })
    assert draw_pro_kline(df, lang="en").data[0].name == "Daily K"
    assert draw_pro_kline(df, lang="zh").data[0].name == "日K"


def test_gemini_prompts_switch_by_lang():
    import pandas as pd

    from webapp import gemini

    snap = pd.DataFrame([
        {
            "ticker": "NVDA", "name": "NVIDIA", "leg": "US", "layer": "L2",
            "arf": 68.0, "decile": 3, "e_score": 90.0, "v_score": 50.0,
            "roe": 1.1, "ps_ratio": 20.0, "froth_flag": False, "price": 130.0,
        }
    ])
    cons = pd.DataFrame([
        {
            "ticker": "NVDA", "n_institutions": 5, "n_reports": 8,
            "rating_summary": "Buy:5", "consensus_target": 150.0,
            "currency": "USD", "implied_upside_pct": 15.4, "eps_forecast": 4.2,
        }
    ])
    res = pd.DataFrame(columns=["ticker", "source", "report_date", "institution", "rating", "title"])
    en_digest = gemini._research_digest(cons, snap, res, lang="en")
    zh_digest = gemini._research_digest(cons, snap, res, lang="zh")
    assert "Sell-side:" in en_digest
    assert not any("\u4e00" <= ch <= "\u9fff" for ch in en_digest)
    assert "卖方:" in zh_digest
    assert not any("\u4e00" <= ch <= "\u9fff" for ch in gemini._RESEARCH_SYSTEM_PROMPT_EN)
    assert not any("\u4e00" <= ch <= "\u9fff" for ch in gemini._ANALYST_SYSTEM_PROMPT_EN)
    assert not any("\u4e00" <= ch <= "\u9fff" for ch in gemini._WEEKLY_SYNTHESIS_SYSTEM_PROMPT_EN)
