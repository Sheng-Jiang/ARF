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
