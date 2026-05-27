from datetime import date
from pathlib import Path

import pandas as pd
import plotly.graph_objects as go


def _fmt(val: object, fmt: str = ".1f") -> str:
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return "—"
    try:
        return format(float(val), fmt)
    except (TypeError, ValueError):
        return str(val)


def _pct(val: object) -> str:
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return "—"
    try:
        return f"{float(val)*100:.1f}%"
    except (TypeError, ValueError):
        return str(val)


def _froth_marker(row: pd.Series) -> str:
    if row.get("froth_flag") is True:
        return "★"
    return ""


def _leg_table(df: pd.DataFrame) -> str:
    cols = [
        ("Ticker", lambda r: r["ticker"]),
        ("Name", lambda r: r.get("name", "")),
        ("Layer", lambda r: r.get("layer", "")),
        ("ARF", lambda r: _fmt(r.get("arf"))),
        ("D", lambda r: _fmt(r.get("decile"), ".0f")),
        ("E", lambda r: _fmt(r.get("e_score"))),
        ("V", lambda r: _fmt(r.get("v_score"))),
        ("Froth", lambda r: "**True** ★" if r.get("froth_flag") else "False"),
        ("Fwd P/E", lambda r: _fmt(r.get("forward_pe"))),
        ("P/S", lambda r: _fmt(r.get("ps_ratio"))),
        ("Rev YoY", lambda r: _pct(r.get("revenue_yoy_growth"))),
        ("ROE", lambda r: _pct(r.get("roe"))),
    ]
    header = " | ".join(c[0] for c in cols)
    sep = " | ".join("---" for _ in cols)
    rows = []
    for _, row in df.sort_values("arf", ascending=False, na_position="last").iterrows():
        rows.append(" | ".join(fn(row) for _, fn in cols))
    return "\n".join([header, sep] + rows)


def _preipo_table(df: pd.DataFrame) -> str:
    header = "Name | Layer | Leg"
    sep = "--- | --- | ---"
    rows = []
    for _, row in df.iterrows():
        rows.append(f"{row.get('name','')} | {row.get('layer','')} | {row.get('leg','')}")
    return "\n".join([header, sep] + rows)


def _europe_table(df: pd.DataFrame) -> str:
    return _preipo_table(df)


def render_markdown(df: pd.DataFrame, as_of: date) -> str:
    us = df[df["leg"] == "US"]
    china = df[df["leg"] == "China"]
    preipo = df[df["leg"] == "Pre-IPO"]
    europe = df[df["leg"] == "Europe-ref"]

    d1_us = int((us["decile"] == 1).sum()) if len(us) else 0
    d1_china = int((china["decile"] == 1).sum()) if len(china) else 0
    froth_us = int((us["froth_flag"] == True).sum()) if len(us) else 0  # noqa: E712
    froth_china = int((china["froth_flag"] == True).sum()) if len(china) else 0  # noqa: E712

    lines = [
        f"# AI Relevance Factor Report — {as_of}",
        "",
        f"**As of:** {as_of}  |  **US names:** {len(us)}  |  **China names:** {len(china)}",
        "",
        "## Bubble Thermometer Summary",
        "",
        "| Leg | D1 count | Froth flags |",
        "| --- | --- | --- |",
        f"| US | {d1_us} | {froth_us} |",
        f"| China | {d1_china} | {froth_china} |",
        "",
        "> ★ = froth flag (D1 + ROE < cost-of-equity + P/S > 25)",
        "",
    ]

    if len(us):
        lines += ["## US Leg", "", _leg_table(us), ""]

    if len(china):
        lines += ["## China Leg", "", _leg_table(china), ""]

    if len(preipo):
        lines += ["## Pre-IPO Sub-Universe", "", _preipo_table(preipo), ""]

    if len(europe):
        lines += ["## Europe Chokepoint Reference", "", _europe_table(europe), ""]

    return "\n".join(lines)


def render_thermometer_html(thermo: pd.DataFrame) -> str:
    """Return a standalone Plotly HTML chart of bubble-thermometer series."""
    fig = go.Figure()

    if len(thermo):
        for leg in thermo["leg"].unique():
            leg_df = thermo[thermo["leg"] == leg].sort_values("as_of_date")
            fig.add_trace(go.Scatter(
                x=leg_df["as_of_date"],
                y=leg_df["count_froth"],
                mode="lines+markers",
                name=f"{leg} — froth count",
            ))
            fig.add_trace(go.Scatter(
                x=leg_df["as_of_date"],
                y=leg_df["count_arf_gte_90"],
                mode="lines+markers",
                name=f"{leg} — ARF ≥ 90 count",
                line={"dash": "dot"},
            ))

    fig.update_layout(
        title="ARF Bubble Thermometer",
        xaxis_title="Date",
        yaxis_title="Count of names",
        hovermode="x unified",
    )
    return fig.to_html(full_html=True, include_plotlyjs="cdn")


def write_report(df: pd.DataFrame, thermo: pd.DataFrame, as_of: date, output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    md = render_markdown(df, as_of=as_of)
    (output_dir / f"arf_{as_of}.md").write_text(md, encoding="utf-8")
    html = render_thermometer_html(thermo)
    (output_dir / "thermometer.html").write_text(html, encoding="utf-8")
