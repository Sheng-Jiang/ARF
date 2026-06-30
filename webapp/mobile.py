"""Mobile-rendering helpers.

Phones can't interact with the dashboard's charts the way a mouse can: a Plotly
or ECharts widget captures touch gestures, so trying to *scroll the page* over a
chart instead pans/zooms it ("floating"). On small screens we therefore render
charts as fixed, non-interactive graphics — they still draw client-side (crisp,
no server-side image export needed) but no longer hijack scrolling.

Detection is a best-effort User-Agent sniff via ``st.context.headers`` (zero
extra dependencies, no rerun). If the header is unavailable we fall back to the
desktop (interactive) experience.
"""
from __future__ import annotations

import streamlit as st

_MOBILE_UA_HINTS = ("mobile", "iphone", "ipod", "android", "windows phone")


def is_mobile() -> bool:
    """Best-effort phone detection from the request User-Agent."""
    try:
        ua = (st.context.headers.get("User-Agent") or "").lower()
    except Exception:  # noqa: BLE001 — st.context may be unavailable in some runtimes
        return False
    # An iPad reports a desktop-class UA and has room for the interactive layout,
    # so it is intentionally treated as desktop.
    return any(hint in ua for hint in _MOBILE_UA_HINTS)


def inject_mobile_css() -> None:
    """Page-level CSS for phones: shrink the (oversized) top title, tighten the
    side gutters, and keep CJK headings from clipping. Safe on desktop — the size
    override is scoped to a ``max-width: 640px`` media query. Call once per page.
    """
    st.markdown(
        "<style>"
        "h1,h2,h3{line-height:1.4!important;overflow:visible}"
        "@media (max-width:640px){"
        ".block-container{padding-left:.7rem;padding-right:.7rem}"
        "h1{font-size:1.75rem!important}"
        "}"
        "</style>",
        unsafe_allow_html=True,
    )


def plotly_config() -> dict:
    """Plotly config: always hide the modebar; on phones freeze the chart into a
    fixed graphic (``staticPlot``) so it never steals page scrolling."""
    cfg: dict = {"displayModeBar": False, "responsive": True}
    if is_mobile():
        cfg["staticPlot"] = True
    return cfg


def show_plotly(fig, **kwargs) -> None:
    """Render a Plotly figure full-width with the mobile-aware config."""
    st.plotly_chart(fig, use_container_width=True, config=plotly_config(), **kwargs)
