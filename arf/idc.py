"""IDC Market Intelligence & MarketScape Engine.

This module bridges ARF quantitative factors into IDC's industry-standard
technology market research methodologies:
1. IDC MarketScape Vendor Analysis: Evaluates AI vendors across Capabilities
   (execution quality, ROE, margins) and Strategies (AI exposure, forward growth, R&D momentum).
2. Worldwide AI Spending & Bubble Gap Tracker: Sizes real economic revenue vs.
   narrative market capitalization across Jensen Huang's 5 layers.
3. Automated IDC Executive Briefing: Synthesizes authoritative research notes
   with 'IDC Opinion', 'Market Outlook', and 'Essential Guidance for Tech Buyers'.
"""

from __future__ import annotations

import logging
from datetime import UTC, date, datetime
from typing import Any

import numpy as np
import pandas as pd

from arf.forecast import _num

log = logging.getLogger(__name__)

# IDC MarketScape Quadrant Thresholds (on a 0-100 standardized scale).
# Public so the chart's quadrant boxes and the data/report classification
# cannot drift apart.
STRATEGY_LEADER_THRESHOLD = 55.0
CAPABILITY_LEADER_THRESHOLD = 52.0

_MARKETSCAPE_COLUMNS = [
    "ticker", "name", "leg", "layer", "price",
    "capabilities_score", "strategies_score", "marketscape_category",
    "market_cap_b", "ai_revenue_est_b", "arf", "e_score", "v_score",
    "roe", "gross_margin", "ps_ratio", "ev_sales", "implied_growth",
    "predicted_growth", "expected_beat_pct", "revision_velocity_14d",
    "froth_flag",
]


def _fmt_pct(value: object, decimals: int = 1, signed: bool = False) -> str:
    """Format a fraction as a percentage, rendering NULL/NaN as ``N/A``.

    ``value is not None`` is not enough here: ``_num`` returns ``None`` but
    once the value round-trips through a float DataFrame column it comes back
    as ``NaN``, which no ``is not None`` guard catches.
    """
    if value is None or pd.isna(value):
        return "N/A"
    try:
        return f"{float(value):+.{decimals}%}" if signed else f"{float(value):.{decimals}%}"
    except (TypeError, ValueError):
        return "N/A"


def _fmt_num(value: object, decimals: int = 1) -> str:
    if value is None or pd.isna(value):
        return "N/A"
    try:
        return f"{float(value):.{decimals}f}"
    except (TypeError, ValueError):
        return "N/A"


def compute_idc_marketscape(
    snap_df: pd.DataFrame,
    fc_df: pd.DataFrame | None = None,
) -> pd.DataFrame:
    """Compute IDC MarketScape Capabilities and Strategies scores for universe vendors.

    Axes:
    - Capabilities (Y-Axis): Current offering strength, financial viability, ROE quality,
      operating margin, and supply-chain pure-play execution.
    - Strategies (X-Axis): Forward growth trajectory, AI Exposure (E_score), consensus
      revision velocity, and predictive beat momentum.

    Returns:
        DataFrame with columns:
        [ticker, name, leg, layer, capabilities_score, strategies_score,
         marketscape_category, market_cap_b, ai_revenue_est_b, arf, froth_flag]
    """
    if snap_df.empty:
        return pd.DataFrame(columns=_MARKETSCAPE_COLUMNS)

    fc_map: dict[str, dict[str, Any]] = {}
    if fc_df is not None and not fc_df.empty:
        for _, r in fc_df.iterrows():
            tk = str(r.get("ticker", "")).strip().upper()
            if not tk:
                continue
            rec = r.to_dict()
            prev = fc_map.get(tk)
            # load_forecasts() orders by expected_beat_pct DESC, so "last row
            # wins" would silently keep the *lowest*-beat revision whenever a
            # ticker has more than one forecast row. Prefer the newest row;
            # ties keep the first (highest-beat) row.
            key = (str(rec.get("as_of_date") or ""), str(rec.get("created_at") or ""))
            if prev is None or key > (
                str(prev.get("as_of_date") or ""),
                str(prev.get("created_at") or ""),
            ):
                fc_map[tk] = rec

    rows = []
    unscored = 0
    for _, r in snap_df.iterrows():
        d = r.to_dict()
        tk = str(d.get("ticker", "")).strip().upper()
        if not tk:
            continue

        # ARF inputs. A vendor without a computed E/V/ARF has not been scored
        # (partial snapshot write, or a display-only Pre-IPO row) and cannot be
        # positioned on the MarketScape honestly. Substituting a mid-point
        # would fabricate a ranking, so drop the row instead.
        e_score = _num(d.get("e_score"))
        v_score = _num(d.get("v_score"))
        arf = _num(d.get("arf"))
        if e_score is None or v_score is None or arf is None:
            unscored += 1
            continue

        name = str(d.get("name") or tk)
        leg = str(d.get("leg") or "US")
        layer = str(d.get("layer") or "L2")
        mcap_usd = _num(d.get("market_cap_usd")) or 0.0
        mcap_b = mcap_usd / 1e9

        # Raw metrics — left as None when the source did not provide them.
        roe = _num(d.get("roe"))
        gross_margin = _num(d.get("gross_margin"))
        rev_growth = _num(d.get("revenue_yoy_growth"))
        froth = bool(d.get("froth_flag"))

        f_data = fc_map.get(tk, {})
        pred_growth = _num(f_data.get("predicted_rev_growth"))
        if pred_growth is None:
            pred_growth = rev_growth if rev_growth is not None else 0.15
        beat_pct = _num(f_data.get("expected_beat_pct"))
        rev_vel = _num(f_data.get("revision_velocity_14d"))
        # Missing consensus inputs are scored neutrally, never as a measured 0.
        beat_for_score = beat_pct if beat_pct is not None else 0.0
        vel_for_score = rev_vel if rev_vel is not None else 0.0

        # Estimated AI revenue = (market cap / EV-Sales) × AI exposure.
        # No multiple means no estimate; do not pretend 10x.
        ev_s = _num(d.get("ev_sales"))
        if ev_s is None:
            ev_s = _num(d.get("ps_ratio"))
        if ev_s is not None and ev_s > 0:
            rev_ttm_b: float | None = mcap_b / ev_s
            ai_rev_b: float | None = rev_ttm_b * (e_score / 100.0)
        else:
            rev_ttm_b = None
            ai_rev_b = None

        # ── 1. Capabilities Score (Y-Axis: Current Financial & Operational Strength)
        # Components: ROE (40%), Gross Margin (25%), E-score (20%), Valuation Quality (15%)
        # Normalization: ROE 0% to 50% -> 30 to 90 pts
        cap_parts: list[tuple[float, float]] = [
            (0.20, float(e_score)),
            (0.15, float(np.clip(100.0 - (v_score * 0.6), 15.0, 90.0))),
        ]
        if roe is not None:
            cap_parts.append((0.40, float(np.clip((roe / 0.40) * 50.0 + 35.0, 10.0, 95.0))))
        if gross_margin is not None:
            cap_parts.append((0.25, float(np.clip(gross_margin * 100.0, 20.0, 95.0))))
        cap_score = round(
            sum(w * c for w, c in cap_parts) / sum(w for w, _ in cap_parts),
            1,
        )

        # ── 2. Strategies Score (X-Axis: Forward AI Growth & Positioning)
        # Components: E_score (35%), Forward Growth (40%), Consensus Beat & Revision (25%)
        fwd_growth_comp = np.clip((pred_growth / 0.50) * 60.0 + 30.0, 15.0, 98.0)
        beat_comp = np.clip(50.0 + beat_for_score * 150.0 + vel_for_score * 200.0, 20.0, 95.0)

        strat_score = round(
            float(0.35 * e_score + 0.40 * fwd_growth_comp + 0.25 * beat_comp),
            1,
        )

        # ── 3. Categorization into IDC MarketScape Quadrants
        if strat_score >= STRATEGY_LEADER_THRESHOLD and cap_score >= CAPABILITY_LEADER_THRESHOLD:
            category = "Leaders"
        elif cap_score >= CAPABILITY_LEADER_THRESHOLD:
            category = "Major Players"
        elif strat_score >= STRATEGY_LEADER_THRESHOLD:
            category = "Contenders"
        else:
            category = "Participants"

        rows.append({
            "ticker": tk,
            "name": name,
            "leg": leg,
            "layer": layer,
            "price": _num(d.get("price")),
            "capabilities_score": cap_score,
            "strategies_score": strat_score,
            "marketscape_category": category,
            "market_cap_b": round(mcap_b, 1),
            "ai_revenue_est_b": None if ai_rev_b is None else round(ai_rev_b, 2),
            "arf": round(arf, 1),
            "e_score": e_score,
            "v_score": v_score,
            "roe": roe,
            "gross_margin": gross_margin,
            "ps_ratio": _num(d.get("ps_ratio")),
            "ev_sales": ev_s,
            "implied_growth": _num(d.get("implied_growth")),
            "predicted_growth": round(pred_growth, 3),
            "expected_beat_pct": None if beat_pct is None else round(beat_pct, 3),
            "revision_velocity_14d": None if rev_vel is None else round(rev_vel, 3),
            "froth_flag": froth,
        })

    if unscored:
        log.info("MarketScape: skipped %d unscored vendor(s) with no ARF", unscored)
    if not rows:
        # Typed empty frame: callers index by column, and a column-less frame
        # is what turned "no scored vendors" into a KeyError downstream.
        return pd.DataFrame(columns=_MARKETSCAPE_COLUMNS)
    df = pd.DataFrame(rows)
    return df.sort_values(["capabilities_score", "strategies_score"], ascending=False).reset_index(drop=True)


_LAYER_NAMES = {
    "zh": {
        "L1": "L1 芯片设计与制造 (Foundry & Chip Design)",
        "L2": "L2 核心互联与硬件 (Hardware & Optical Interconnect)",
        "L3": "L3 基础设施与云厂商 (Infrastructure & Hyperscalers)",
        "L4": "L4 基础大模型与开发平台 (Foundation Models & Platforms)",
        "L5": "L5 垂直行业应用与智能体 (Enterprise Apps & Agentic AI)",
    },
    "en": {
        "L1": "L1 Chip Design & Foundry",
        "L2": "L2 Hardware & Optical Interconnect",
        "L3": "L3 Infrastructure & Hyperscalers",
        "L4": "L4 Foundation Models & Platforms",
        "L5": "L5 Enterprise Apps & Agentic AI",
    },
}


def compute_ai_spending_tracker(snap_df: pd.DataFrame, lang: str = "zh") -> dict[str, Any]:
    """Size the worldwide AI market across Jensen's 5 layers, comparing real revenue to valuation.

    Returns structured summary with market cap, estimated AI spending/revenue,
    bubble multiplier, and layer-by-layer breakdowns. ``lang`` selects the
    display language for ``layer_name`` ('zh' or 'en').
    """
    if snap_df.empty:
        return {}

    layer_names = _LAYER_NAMES.get(lang, _LAYER_NAMES["zh"])

    df = snap_df.copy()
    df["mcap_usd"] = df["market_cap_usd"].apply(lambda x: _num(x) or 0.0)
    df["ev_s"] = df["ev_sales"].fillna(df["ps_ratio"]).apply(_num)
    df["e_score_val"] = df["e_score"].apply(_num)

    # Only a vendor with a market cap, a valuation multiple and a computed
    # exposure score has an estimable AI revenue. Pre-IPO / manual rows carry
    # market cap 0 and NULL scores; including them would add $0 of market cap
    # but inflate vendor_count and dilute the bubble multiple with invented
    # revenue. Restrict the tracker to the scored universe.
    df = df[
        (df["mcap_usd"] > 0)
        & df["ev_s"].apply(lambda x: x is not None and x > 0)
        & df["e_score_val"].notna()
    ].copy()

    # Revenue estimate = (Market Cap / EV_Sales) * (E_score / 100)
    df["est_rev_ttm_usd"] = df["mcap_usd"] / df["ev_s"]
    df["est_ai_rev_usd"] = df["est_rev_ttm_usd"] * (df["e_score_val"] / 100.0)

    total_mcap_usd = float(df["mcap_usd"].sum())
    total_ai_rev_usd = float(df["est_ai_rev_usd"].sum())
    overall_bubble_multiple = (
        round(total_mcap_usd / total_ai_rev_usd, 1) if total_ai_rev_usd > 0 else 0.0
    )

    # Layer breakdown
    layer_stats = []
    for l_key, l_label in layer_names.items():
        sub = df[df["layer"] == l_key]
        if sub.empty:
            continue
        l_mcap_b = float(sub["mcap_usd"].sum()) / 1e9
        l_ai_rev_b = float(sub["est_ai_rev_usd"].sum()) / 1e9
        mult = round(l_mcap_b / l_ai_rev_b, 1) if l_ai_rev_b > 0 else 0.0
        froth_names = sub[sub["froth_flag"] == True]["ticker"].tolist()  # noqa: E712
        top_players = sub.sort_values("mcap_usd", ascending=False).head(3)["name"].tolist()

        layer_stats.append({
            "layer_code": l_key,
            "layer_name": l_label,
            "vendor_count": len(sub),
            "market_cap_b": round(l_mcap_b, 1),
            "ai_revenue_est_b": round(l_ai_rev_b, 1),
            "bubble_multiple": mult,
            "froth_count": len(froth_names),
            "top_vendors": ", ".join(top_players),
        })

    # Leg breakdown
    leg_stats = {}
    for leg in ("US", "China"):
        sub = df[df["leg"] == leg]
        l_mcap_b = float(sub["mcap_usd"].sum()) / 1e9
        l_ai_rev_b = float(sub["est_ai_rev_usd"].sum()) / 1e9
        leg_stats[leg] = {
            "market_cap_b": round(l_mcap_b, 1),
            "ai_revenue_est_b": round(l_ai_rev_b, 1),
            "bubble_multiple": round(l_mcap_b / l_ai_rev_b, 1) if l_ai_rev_b > 0 else 0.0,
            "count": len(sub),
        }

    return {
        "as_of_date": snap_df["as_of_date"].iloc[0] if "as_of_date" in snap_df.columns else str(date.today()),
        "total_universe_mcap_t": round(total_mcap_usd / 1e12, 2),
        "total_ai_revenue_b": round(total_ai_rev_usd / 1e9, 1),
        "overall_bubble_multiple": overall_bubble_multiple,
        "covered_count": len(df),
        "layers": layer_stats,
        "legs": leg_stats,
    }


def generate_idc_executive_briefing(
    as_of: date,
    snap_df: pd.DataFrame,
    fc_df: pd.DataFrame | None = None,
    lang: str = "zh",
) -> str:
    """Generate an authoritative IDC Executive Market Briefing in official IDC research format.
    
    Args:
        as_of: Snapshot date.
        snap_df: Evaluated universe snapshot DataFrame.
        fc_df: Optional forward forecasts DataFrame.
        lang: 'zh' for Chinese or 'en' for English.
    """
    ms_df = compute_idc_marketscape(snap_df, fc_df)
    spending = compute_ai_spending_tracker(snap_df, lang=lang)

    doc_id = f"IDC-MR-{as_of.strftime('%Y%m')}-{as_of.strftime('%d')}"
    if ms_df.empty:
        if lang == "en":
            return (
                "# 🌐 IDC MarketScape & Worldwide AI Spending Guide\n"
                f"**Document ID:** `{doc_id}`\n\n"
                "> No scored vendors found for this snapshot date. "
                "Please select a fully scored snapshot and retry."
            )
        return (
            "# 🌐 IDC MarketScape & Worldwide AI Spending Guide\n"
            f"**Document ID:** `{doc_id}`\n\n"
            "> 该快照尚无已完成评分的厂商，无法生成 MarketScape 简报。"
            "请选择已完成评分的快照日期后重试。"
        )

    leaders = ms_df[ms_df["marketscape_category"] == "Leaders"].head(5)
    contenders = ms_df[ms_df["marketscape_category"] == "Contenders"].head(4)
    froth_list = ms_df[ms_df["froth_flag"] == True]["ticker"].tolist()  # noqa: E712
    covered_count = int(spending.get("covered_count", len(ms_df)))

    timestamp = datetime.now(UTC).strftime("%B %d, %Y")

    if lang == "en":
        lines = [
            "# 🌐 IDC MarketScape & Worldwide AI Spending Guide",
            f"**Document ID:** `{doc_id}` | **Published:** `{timestamp}` | **Program:** *AI, Software & Infrastructure Strategies*",
            "**Author:** *Sheng Jiang, Vice President, AI Market Research & Strategy*",
            "",
            "---",
            "",
            "## 1. IDC Opinion (Executive Summary & Key Theses)",
            f"> **Market Perspective**: As of {as_of.isoformat()}, the aggregate market capitalization of the {covered_count} scored global AI leaders stands at **${spending.get('total_universe_mcap_t', 0.0)} Trillion USD**, "
            f"supported by **${spending.get('total_ai_revenue_b', 0.0)} Billion USD** in purity-adjusted annualized economic AI revenue, "
            f"yielding an overall narrative valuation multiple of **{spending.get('overall_bubble_multiple', 0.0)}x**.",
            "",
            "- **Value Aggregates at Physical Bottlenecks**: Midstream and upstream hardware infrastructure—notably CoWoS advanced packaging, 800G/1.6T optical transceivers, and datacenter high-voltage grid capacity—captures peak margin conversion (Capabilities scores outperforming);",
            "- **Downstream Software & Agent Multiple Compression**: Layer 5 application wrappers lacking proprietary data flywheels face severe valuation de-rating; several high-ARF names have triggered froth circuit breakers;",
            f"- **Froth Alert Watchlist**: Currently `{len(froth_list)}` vendors have breached the hard froth circuit breaker (including `{', '.join(froth_list) if froth_list else 'None'}`).",
            "",
            "---",
            "",
            "## 2. IDC MarketScape: Global AI Vendors Assessment",
            "The IDC MarketScape employs a quantitative dual-axis evaluation model, assessing vendors along **Capabilities (Execution Quality & Financial Moat)** and **Strategies (Forward Growth & AI Exposure)**:",
            "",
            "### 🏆 Leaders Quadrant",
            "Leaders demonstrate superior returns on equity (ROE > 25%), robust free cash flows, and defensible architectural moats:",
            "| Ticker | Vendor Name | Leg | Stack Layer | Capabilities | Strategies | Market Cap (USD) | 12M Forecast Growth |",
            "| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |",
        ]
        for _, lr in leaders.iterrows():
            pg_str = _fmt_pct(lr.get("predicted_growth"), signed=True)
            lines.append(
                f"| **{lr['ticker']}** | {lr['name']} | `{lr['leg']}` | `{lr['layer']}` | "
                f"**{lr['capabilities_score']:.1f}** | **{lr['strategies_score']:.1f}** | "
                f"${lr['market_cap_b']:.1f}B | {pg_str} |"
            )
        lines.append("")

        lines.append("### ⚡ Contenders Quadrant (High-Beta Growth)")
        lines.append("Vendors possessing exceptional strategic exposure and forward revenue momentum, accompanied by higher delivery margin volatility:")
        lines.append("| Ticker | Vendor Name | Leg | Stack Layer | Capabilities | Strategies | ARF Score | Froth Status |")
        lines.append("| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |")
        for _, cr in contenders.iterrows():
            f_badge = "🔴 FROTH WARNING" if cr["froth_flag"] else "🟢 NORMAL"
            lines.append(
                f"| **{cr['ticker']}** | {cr['name']} | `{cr['leg']}` | `{cr['layer']}` | "
                f"{cr['capabilities_score']:.1f} | **{cr['strategies_score']:.1f}** | "
                f"`{cr['arf']:.1f}` | {f_badge} |"
            )
        lines.append("")

        lines.extend([
            "---",
            "",
            "## 3. Worldwide AI Spending & Bubble Gap Analysis",
            "| AI Stack Layer | Scored Vendors | Equity Market Cap (USD) | Real Economic AI Revenue | Narrative Bubble Multiple | Valuation Stance | Representative Leaders |",
            "| :--- | :--- | :--- | :--- | :--- | :--- | :--- |",
        ])
        for l_stat in spending.get("layers", []):
            f_count = l_stat["froth_count"]
            status = "🔴 Overheating" if f_count > 0 or l_stat["bubble_multiple"] > 35 else "🟢 Balanced"
            lines.append(
                f"| **{l_stat['layer_name']}** | {l_stat['vendor_count']} | ${l_stat['market_cap_b']:.1f}B | "
                f"${l_stat['ai_revenue_est_b']:.1f}B | **{l_stat['bubble_multiple']:.1f}x** | {status} | "
                f"{l_stat['top_vendors']} |"
            )
        lines.append("")

        lines.extend([
            "---",
            "",
            "## 4. Essential Guidance for Technology Buyers (CIO / CTO)",
            "1. **Scrutinize Layer 5 Application Valuations**: Prioritize vendors with proprietary workflow data moats and verified employee-productivity gains. For thin prompt-wrapper apps without unique IP, negotiate short subscription terms or pilot internal open-source alternatives.",
            "2. **Secure Midstream Supply-Chain Allocations**: Physical compute bottlenecks (CoWoS packaging, 800G+ optical transceivers) remain hard constraints over the next 4 quarters. Enterprise procurement must establish dual-sourcing agreements across both US and China supply-chain corridors.",
            "3. **Benchmark Business Viability via Reverse-DCF Implied Growth**: When a vendor's implied perpetual growth rate exceeds twice your internal IT budget expansion rate, their pricing cycle is late-stage, offering favorable commercial renegotiation windows.",
            "",
            "## 5. Essential Guidance for Technology Vendors (CEO / CRO)",
            "1. **Shift Focus from Raw Compute to Unit Tokenomics**: With open-source model convergence and distillation diffusion, vendor pricing power is migrating to full-stack inference efficiency and vertical systems integration.",
            "2. **Establish Counter-Cyclical Valuation Defenses**: Vendors in the high-ARF froth territory (Decile 1) face severe multiple de-rating risks. Take advantage of high-valuation windows to accelerate strategic acquisitions, reinforce balance-sheet cash reserves, and strengthen ROE fundamentals.",
            "",
            "---",
            "*Report compiled by IDC AI & Software Research Practice using ARF Quantitative Methodology. Copyright © 2026 IDC. All rights reserved.*",
        ])
        return "\n".join(lines)

    lines = [
        "# 🌐 IDC MarketScape & Worldwide AI Spending Guide",
        f"**Document ID:** `{doc_id}` | **Published:** `{timestamp}` | **Program:** *AI, Software & Infrastructure Strategies*",
        "**Author:** *Sheng Jiang, Vice President, AI Market Research & Strategy*",
        "",
        "---",
        "",
        "## 1. IDC Opinion (执行摘要与核心论点)",
        f"> **市场整体定调**：截至 {as_of.isoformat()}，全球核心 {covered_count} 家已评分 AI 标的的总市值为 **${spending.get('total_universe_mcap_t', 0.0)} 万亿美元**，"
        f"对应本研究测算的经纯度折算后的年化实质 AI 收入为 **${spending.get('total_ai_revenue_b', 0.0)} 十亿美元**，"
        f"全行业整体「叙事市值 / 实质收入」估值倍数达到 **{spending.get('overall_bubble_multiple', 0.0)}x**。",
        "",
        "- **价值向中上游物理瓶颈汇聚**：以 CoWoS 封装、800G/1.6T 光模块、数据中心高压电力为代表的物理瓶颈层级享有最高的利润转化率（Capabilities 分数显著领跑）；",
        "- **下游软件与智能体面临估值消融**：Layer 5 纯套壳智能体与未构建私有数据飞轮的应用面临高估值消化压力，部分高 ARF 标的已亮起泡沫熔断告警；",
        f"- **重点告警名单**：当前全市场共有 `{len(froth_list)}` 家标的触发硬性泡沫熔断 (Froth Circuit Breaker)（包括 `{', '.join(froth_list) if froth_list else '无'}`）。",
        "",
        "---",
        "",
        "## 2. IDC MarketScape: 全球 AI 核心厂商竞争全景矩阵",
        "IDC MarketScape 采用严密的定量双轴评价体系，从 **Capabilities (现行交付与财务质量)** 和 **Strategies (未来战略与增长弹性)** 两个维度对厂商进行定位：",
        "",
    ]

    # Leaders section
    lines.append("### 🏆 领军者阵营 (Leaders)")
    lines.append("领军者具备顶级资产收益率 (ROE > 25%)、健康的自由现金流以及确定性极高的技术壁垒：")
    lines.append("| 厂商代码 | 公司名称 | 区域 | 产业链层级 | 交付质量 (Capabilities) | 战略动能 (Strategies) | 市值 (USD) | 12M预测增速 |")
    lines.append("| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |")
    for _, lr in leaders.iterrows():
        pg_str = _fmt_pct(lr.get("predicted_growth"), signed=True)
        lines.append(
            f"| **{lr['ticker']}** | {lr['name']} | `{lr['leg']}` | `{lr['layer']}` | "
            f"**{lr['capabilities_score']:.1f}** | **{lr['strategies_score']:.1f}** | "
            f"${lr['market_cap_b']:.1f}B | {pg_str} |"
        )
    lines.append("")

    # Contenders section
    lines.append("### ⚡ 挑战者与高弹性阵营 (Contenders)")
    lines.append("具备极高的战略暴露度与前瞻增速，但在当期交付利润率或估值张力上呈现出高波动性：")
    lines.append("| 厂商代码 | 公司名称 | 区域 | 产业链层级 | 交付质量 | 战略动能 | ARF 分值 | 泡沫告警 |")
    lines.append("| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |")
    for _, cr in contenders.iterrows():
        f_badge = "🔴 泡沫预警" if cr["froth_flag"] else "🟢 正常"
        lines.append(
            f"| **{cr['ticker']}** | {cr['name']} | `{cr['leg']}` | `{cr['layer']}` | "
            f"{cr['capabilities_score']:.1f} | **{cr['strategies_score']:.1f}** | "
            f"`{cr['arf']:.1f}` | {f_badge} |"
        )
    lines.append("")

    # Spending Guide Table
    lines.extend([
        "---",
        "",
        "## 3. 全球 AI 产业支出与泡沫乘数分布 (Worldwide AI Spending & Bubble Gap)",
        "| 产业链层级 | 纳管厂商数 | 资本市值 (USD) | 实质 AI 收入 (USD) | 叙事泡沫乘数 | 估值状态 | 头部代表厂商 |",
        "| :--- | :--- | :--- | :--- | :--- | :--- | :--- |",
    ])
    for l_stat in spending.get("layers", []):
        f_count = l_stat["froth_count"]
        status = "🔴 局部过热" if f_count > 0 or l_stat["bubble_multiple"] > 35 else "🟢 健康匹配"
        lines.append(
            f"| **{l_stat['layer_name']}** | {l_stat['vendor_count']} | ${l_stat['market_cap_b']:.1f}B | "
            f"${l_stat['ai_revenue_est_b']:.1f}B | **{l_stat['bubble_multiple']:.1f}x** | {status} | "
            f"{l_stat['top_vendors']} |"
        )
    lines.append("")

    # Essential Guidance
    lines.extend([
        "---",
        "",
        "## 4. Essential Guidance for Technology Buyers (CIO / CTO 决策指南)",
        "1. **警惕 Layer 5 应用层高估值陷阱**：优先采购具备「专有工作流数据护城河」与「实际人效节省验证」的厂商；对于缺乏私有数据的纯 Prompt 包装软件，建议采取审慎订阅或自建开源替代方案。",
        "2. **锁定中游供应链交付配额**：物理算力瓶颈（CoWoS、800G+ 光模块）在未来 4 个季度仍是硬约束，建议企业 IT 采购提前锁定多源供应商（Dual-Sourcing），特别是在中美双轨供应链中保持采购弹性。",
        "3. **以逆向 DCF 隐含增长反推商业可行性**：当供应商估值隐含的永续增长率超过客户自身 IT 预算年均复合增速的 2 倍时，该供应商的提价周期已处于晚期，买方具备更强的商务议价窗口。",
        "",
        "## 5. Essential Guidance for Technology Vendors (CEO / 战略高管指南)",
        "1. **从纯算力比拼转向单位 Token 经济学 (Tokenomics)**：面对模型开源化与蒸馏技术扩散，厂商的定价权正在向系统级效能与垂直行业工程化能力转移。",
        "2. **建立逆向估值防线**：高度警惕高 ARF 泡沫区（D1 分位）带来的估值重估风险，应利用高估值窗口期加快战略性 M&A 与技术资产沉淀，提升 ROE 底色以夯实 Capabilities 护城河。",
        "",
        "---",
        "*Report compiled by IDC AI & Software Research Practice using ARF Quantitative Methodology. Copyright © 2026 IDC. All rights reserved.*",
    ])

    return "\n".join(lines)


def generate_analyst_vendor_profile(
    ticker: str,
    snap_df: pd.DataFrame,
    fc_df: pd.DataFrame | None = None,
    links_df: pd.DataFrame | None = None,
    analyst_commentary: str = "",
    lang: str = "zh",
) -> str:
    """Generate a high-density 1-page IDC Vendor Profile & Flash Note for research analysts.
    
    Args:
        ticker: Ticker symbol.
        snap_df: Evaluated universe snapshot DataFrame.
        fc_df: Optional forward forecasts DataFrame.
        links_df: Optional supply chain topology DataFrame.
        analyst_commentary: Custom analyst notes.
        lang: 'zh' for Chinese or 'en' for English.
    """
    ms_df = compute_idc_marketscape(snap_df, fc_df)
    target = str(ticker).strip().upper()
    if ms_df.empty or "ticker" not in ms_df.columns:
        return f"# ❌ Vendor {target} not found in current coverage universe."

    v_rows = ms_df[ms_df["ticker"] == target]
    if v_rows.empty:
        return f"# ❌ Vendor {target} not found in current coverage universe."

    v = v_rows.iloc[0].to_dict()
    as_of_val = snap_df["as_of_date"].iloc[0] if "as_of_date" in snap_df.columns else date.today()
    doc_id = f"IDC-VP-{target}-{datetime.now(UTC).strftime('%Y%m%d')}"

    # Extract supply chain links if available
    cust_links = []
    supp_links = []
    if links_df is not None and not links_df.empty:
        c_sub = links_df[links_df["supplier_ticker"].astype(str).str.upper() == target]
        for _, cr in c_sub.iterrows():
            share = _fmt_num(cr.get("revenue_share_pct"), 0)
            cust_links.append(f"{cr['customer_ticker']} ({share}% rev share)")
        s_sub = links_df[links_df["customer_ticker"].astype(str).str.upper() == target]
        for _, sr in s_sub.iterrows():
            supp_links.append(f"{sr['supplier_ticker']} ({sr.get('relationship_type', 'supplier')})")

    if lang == "en":
        cust_str = ", ".join(cust_links) if cust_links else "No direct customer disclosures / end consumer facing"
        supp_str = ", ".join(supp_links) if supp_links else "No direct upstream disclosures / vertically integrated"
    else:
        cust_str = ", ".join(cust_links) if cust_links else "无直连主要客户申报或处于消费端终端"
        supp_str = ", ".join(supp_links) if supp_links else "无直连主要上游申报或全栈垂直整合"

    pg_str = _fmt_pct(v.get("predicted_growth"), signed=True)
    beat_str = _fmt_pct(v.get("expected_beat_pct"), signed=True)
    vel_str = _fmt_pct(v.get("revision_velocity_14d"), signed=True)
    roe_str = _fmt_pct(v.get("roe"))
    impg_str = _fmt_pct(v.get("implied_growth"))
    ps = _num(v.get("ps_ratio"))
    ps_str = f"{ps:.1f}x" if ps is not None else "N/A"
    ai_rev = _num(v.get("ai_revenue_est_b"))
    ai_rev_str = f"${ai_rev:.2f}B" if ai_rev is not None else "N/A"

    if lang == "en":
        lines = [
            f"# 🔬 IDC Vendor Profile & Flash Note: {v['name']} ({target})",
            f"**Document ID:** `{doc_id}` | **Coverage Desk:** *AI Hardware, Software & Infrastructure*",
            f"**Analyst:** *Sheng Jiang, VP, AI Market Research & Strategy* | **As-Of:** `{as_of_val}`",
            f"**MarketScape Positioning:** 🏅 **{v['marketscape_category']}** | **Froth Circuit:** {'🔴 BREACHED' if v['froth_flag'] else '🟢 NORMAL'}",
            "",
            "---",
            "",
            "## 1. IDC MarketScape™ Quantitative Breakdown",
            f"- **Capabilities Score (Execution Quality & Margins):** `{v['capabilities_score']:.1f} / 100`",
            f"- **Strategies Score (Forward Growth & AI Exposure):** `{v['strategies_score']:.1f} / 100`",
            f"- **Ecosystem Affiliation:** `{v['leg']} Value Chain / {v['layer']} Layer` | **Market Cap:** `${v['market_cap_b']:.1f}B USD`",
            f"- **Estimated Real AI Revenue (Annualized):** `{ai_rev_str} USD` | **AI Pure-Play Exposure (E_score):** `{v.get('e_score', 0):.0f} / 100`",
            "",
            "## 2. Supply Chain Topology & Dependencies",
            f"- **Key Direct Customers:** {cust_str}",
            f"- **Key Upstream Suppliers:** {supp_str}",
            "",
            "## 3. Financial Quality & Bubble Audit",
            f"- **ROE (Return on Equity):** `{roe_str}` (Adjusted for non-recurring items in China A-shares)",
            f"- **Price-to-Sales (P/S Ratio):** `{ps_str}` | **Valuation Stretch (V_score):** `{v.get('v_score', 0):.0f} / 100`",
            f"- **Reverse-DCF Implied Growth (Implied g*):** `{impg_str}`",
            f"- **Composite ARF Score:** `{v.get('arf', 0):.1f}`",
            "",
            "## 4. Forward Forecast & Consensus Dynamics",
            f"- **12M Forward Revenue Forecast (ARF ĝ):** `{pg_str}`",
            f"- **Expected Beat Margin vs Consensus:** `{beat_str}`",
            f"- **14-Day Consensus Revision Velocity:** `{vel_str}`",
            "",
        ]

        if analyst_commentary.strip():
            lines.extend([
                "## 5. IDC Analyst Custom Commentary",
                f"> {analyst_commentary.strip()}",
                "",
            ])

        lines.extend([
            "## 6. IDC Essential Guidance for Technology Buyers",
            f"- For enterprise CIOs/CTOs evaluating solutions from **{v['name']}**: Given their current positioning in the `{v['marketscape_category']}` quadrant, "
            f"if market-implied growth rates substantially outpace your internal IT budget expansion rate, prioritize locking in multi-year price caps and performance SLAs during contract renewal.",
            "",
            "---",
            "*IDC Quanta™ Research Desk Platform. Confident decision-making backed by quantitative data.*",
        ])
        return "\n".join(lines)

    lines = [
        f"# 🔬 IDC Vendor Profile & Flash Note: {v['name']} ({target})",
        f"**Document ID:** `{doc_id}` | **Coverage Desk:** *AI Hardware, Software & Infrastructure*",
        f"**Analyst:** *Sheng Jiang, VP, AI Market Research & Strategy* | **As-Of:** `{as_of_val}`",
        f"**MarketScape Positioning:** 🏅 **{v['marketscape_category']}** | **Froth Circuit:** {'🔴 BREACHED' if v['froth_flag'] else '🟢 NORMAL'}",
        "",
        "---",
        "",
        "## 1. IDC MarketScape™ Quantitative Breakdown",
        f"- **Capabilities Score (当前交付与财务质量):** `{v['capabilities_score']:.1f} / 100`",
        f"- **Strategies Score (未来战略与增长动能):** `{v['strategies_score']:.1f} / 100`",
        f"- **产业链归属:** `{v['leg']} 价值链 / {v['layer']} 层级` | **总市值:** `${v['market_cap_b']:.1f}B USD`",
        f"- **实质 AI 估算收入 (年化):** `{ai_rev_str} USD` | **AI 纯度暴露 (E_score):** `{v.get('e_score', 0):.0f} / 100`",
        "",
        "## 2. 产业链传导与客户依赖拓扑 (Supply Chain Topology)",
        f"- **主要下游客户 (Direct Customers):** {cust_str}",
        f"- **关键上游供应商 (Key Upstream Suppliers):** {supp_str}",
        "",
        "## 3. 财务质量与估值张力分析 (Financial Quality & Bubble Audit)",
        f"- **ROE (净资产收益率):** `{roe_str}` (中股采用扣非净利)",
        f"- **市销率 (P/S Ratio):** `{ps_str}` | **估值张力 (V_score):** `{v.get('v_score', 0):.0f} / 100`",
        f"- **逆向 DCF 隐含增长率 (Implied g*):** `{impg_str}`",
        f"- **ARF 综合指数:** `{v.get('arf', 0):.1f}`",
        "",
        "## 4. 前瞻超预期弹性与一致预期动能 (Predictive Forecast & Consensus Outlook)",
        f"- **12M 前瞻预测营收增速 (ARF ĝ):** `{pg_str}`",
        f"- **超一致预期差 (Expected Beat Margin):** `{beat_str}`",
        f"- **前 14 天一致预期修正动能 (Revision Velocity):** `{vel_str}`",
        "",
    ]

    if analyst_commentary.strip():
        lines.extend([
            "## 5. IDC Analyst Custom Commentary (分析师独家洞察)",
            f"> {analyst_commentary.strip()}",
            "",
        ])

    lines.extend([
        "## 6. IDC Essential Guidance for Buyers",
        f"- 对采购 **{v['name']}** 解决方案的企业 CIO/CTO：结合其当前处于 `{v['marketscape_category']}` 的竞争站位，"
        f"若其隐含增长率高于业务实际 IT 预算扩张节奏，应在合同续约中重点锁定价格上限与交付服务等级协议 (SLA)。",
        "",
        "---",
        "*IDC Quanta™ Research Desk Platform. Confident decision-making backed by quantitative data.*",
    ])

    return "\n".join(lines)

