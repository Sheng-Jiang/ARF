"""Quarterly pool rotation for the 50/50 universe.

Scores every in-pool name on four inactivity dimensions — higher score means
more likely to be swapped out:

- **L (liquidity)**: 90-day average daily turnover in local currency. Below a
  per-leg threshold (US $10M, China ¥100M) scores badly.
- **Q (data quality)**: key-field coverage in the latest snapshot (price, ROE,
  P/S, ARF). Missing fields score badly.
- **H (volume fade)**: 30-day average volume vs the prior 60 days. Halved
  volume is a "dead water" signal.
- **I (ranking inertia)**: |ΔARF| between the two latest snapshots. A flat
  percentile contributes no information.

Watchlist candidates are scored on new-listing signal (``listed_at`` ≤ 12
months → auto-candidate), liquidity (when price history exists) and narrative
heat (research coverage when available).

Rotation swaps at most ``POOL_ROTATION_MAX`` names per leg per quarter,
matching cohort (core→core, newcomer→newcomer) so the 45+5 structure is
preserved, applies the new pool to ``config/universe.yaml``, archives the
membership in ``pool_membership``, records each swap in ``pool_changes``, and
writes a human-readable rotation report.
"""
from __future__ import annotations

import logging
from datetime import date, timedelta
from pathlib import Path

import pandas as pd
import yaml

log = logging.getLogger(__name__)

POOL_ROTATION_MAX = 3  # max swaps per leg per quarter

# Daily-average-turnover thresholds (local currency) below which a name is
# considered illiquid. US in USD, China in CNY (HK names are liquid in HKD;
# treated with the China threshold for simplicity).
LIQUIDITY_THRESHOLDS = {"US": 10e6, "China": 100e6}

# Inactivity composite weights.
L_WEIGHT, Q_WEIGHT, H_WEIGHT, I_WEIGHT = 0.4, 0.3, 0.2, 0.1

# Key fields whose absence in the latest snapshot hurts the Q score.
QUALITY_FIELDS = ("price", "roe", "ps_ratio", "arf")

# New-listing window for the "exciting newcomer" signal.
NEW_LISTING_MONTHS = 12

# Neutral score when a dimension has no data.
NEUTRAL = 50.0


# ── Dimension helpers ────────────────────────────────────────────────────────

def _is_a_share(ticker: str) -> bool:
    return ticker.endswith((".SZ", ".SH"))


def _ticker_history(prices: pd.DataFrame, ticker: str) -> pd.DataFrame:
    """Date-ascending price history for one ticker.

    ``daily_prices`` is read without an ORDER BY guarantee and is UPSERTed in
    partial refreshes, so row order in the frame is arbitrary — every window
    below slices by position and would otherwise score a random historical
    stretch instead of the most recent one.
    """
    df = prices[prices["ticker"] == ticker]
    if df.empty or "date" not in df.columns:
        return df
    return df.sort_values("date")


def _turnover(prices: pd.DataFrame, ticker: str, days: int = 90) -> float | None:
    """90-day average daily turnover in local currency (volume in shares)."""
    df = _ticker_history(prices, ticker).tail(days)
    if df.empty:
        return None
    mult = 100.0 if _is_a_share(ticker) else 1.0  # A-share volume is in hands
    turnover = (df["close"] * df["volume"] * mult).dropna()
    if turnover.empty:
        return None
    return float(turnover.mean())


def _volume_avg(
    prices: pd.DataFrame, ticker: str, days: int, offset: int = 0
) -> float | None:
    """Average daily volume over ``days`` bars ending ``offset`` bars back.

    ``offset=0`` is the most recent ``days`` bars; ``offset=30`` is the ``days``
    bars immediately preceding the last 30.
    """
    df = _ticker_history(prices, ticker)
    if df.empty:
        return None
    end = len(df) - offset
    if end <= 0:
        return None
    df = df.iloc[max(0, end - days):end]
    if df.empty:
        return None
    mult = 100.0 if _is_a_share(ticker) else 1.0
    vols = (df["volume"] * mult).dropna()
    return float(vols.mean()) if not vols.empty else None


def _fade_score(prices: pd.DataFrame, ticker: str) -> float:
    """Volume fade: recent 30d vs the 60d *before* it. Halved volume → 100.

    The two windows must not overlap: comparing the last 30 bars against a
    90-bar window that contains them compresses a genuine 50% fade to a ratio
    of ~0.6 (score 40) — below the NEUTRAL 50 handed to a name with no price
    data at all, which inverts the ranking this dimension exists to produce.
    """
    recent = _volume_avg(prices, ticker, 30)
    prior = _volume_avg(prices, ticker, 60, offset=30)
    if recent is None or prior is None or prior <= 0:
        return NEUTRAL
    ratio = recent / prior
    return float(max(0.0, min(100.0, (1.0 - ratio) * 100.0)))


def _inertia_score(snapshots: pd.DataFrame, ticker: str) -> float:
    """Ranking inertia from the two latest snapshots: |ΔARF| < 1 → 100."""
    df = snapshots[snapshots["ticker"] == ticker].dropna(subset=["arf"])
    if len(df) < 2:
        return NEUTRAL
    df = df.sort_values("as_of_date")
    delta = abs(float(df["arf"].iloc[-1]) - float(df["arf"].iloc[-2]))
    if delta < 1.0:
        return 100.0
    if delta < 5.0:
        return 50.0
    return 0.0


# ── Scoring ──────────────────────────────────────────────────────────────────

def inactivity_scores(
    snapshot_df: pd.DataFrame,
    prices_df: pd.DataFrame,
) -> pd.DataFrame:
    """Per-name inactivity scores for every scored US/China row in snapshot_df.

    ``snapshot_df`` must carry ticker/leg/arf plus QUALITY_FIELDS; the latest
    snapshot per ticker is used for Q. ``prices_df`` carries the daily
    ticker/date/close/volume history used for L and H.
    """
    rows: list[dict] = []
    # Latest snapshot per ticker for the Q dimension.
    latest = (
        snapshot_df[snapshot_df["leg"].isin(["US", "China"])]
        .sort_values("as_of_date")
        .drop_duplicates(subset=["ticker"], keep="last")
    )
    for _, r in latest.iterrows():
        ticker = str(r["ticker"])
        leg = str(r["leg"])

        turnover = _turnover(prices_df, ticker)
        threshold = LIQUIDITY_THRESHOLDS.get(leg, 10e6)
        if turnover is None:
            l_score = NEUTRAL
        else:
            l_score = float(max(0.0, min(100.0, 100.0 - turnover / threshold * 100.0)))

        missing = sum(
            1 for f in QUALITY_FIELDS if r.get(f) is None or pd.isna(r.get(f))
        )
        q_score = float(missing / len(QUALITY_FIELDS) * 100.0)

        h_score = _fade_score(prices_df, ticker)
        i_score = _inertia_score(snapshot_df, ticker)

        composite = (
            L_WEIGHT * l_score + Q_WEIGHT * q_score
            + H_WEIGHT * h_score + I_WEIGHT * i_score
        )
        rows.append({
            "ticker": ticker,
            "leg": leg,
            "cohort": r.get("cohort", "core"),
            "liquidity_score": round(l_score, 1),
            "quality_score": round(q_score, 1),
            "fade_score": round(h_score, 1),
            "inertia_score": round(i_score, 1),
            "inactivity_score": round(composite, 1),
        })
    return pd.DataFrame(rows)


def entrant_scores(
    watch_entries: list,
    prices_df: pd.DataFrame,
    research_df: pd.DataFrame | None = None,
    as_of: date | None = None,
) -> pd.DataFrame:
    """Score watchlist candidates for entry.

    ``watch_entries``: UniverseEntry-like objects with ticker/leg/cohort/
    listed_at. New listing (≤ 12 months before ``as_of``) is a strong signal;
    liquidity uses price history when present; narrative heat uses research
    report counts when available. Missing data yields neutral scores.
    """
    rows: list[dict] = []
    for e in watch_entries:
        ticker = e.ticker
        leg = e.leg

        new_listing = 0.0
        if (
            e.listed_at is not None
            and as_of is not None
            and e.listed_at >= as_of - timedelta(days=30 * NEW_LISTING_MONTHS)
        ):
            new_listing = 100.0

        turnover = _turnover(prices_df, ticker)
        threshold = LIQUIDITY_THRESHOLDS.get(leg, 10e6)
        if turnover is None:
            liq = NEUTRAL
        else:
            liq = float(max(0.0, min(100.0, turnover / threshold * 100.0)))

        heat = NEUTRAL
        if research_df is not None and not research_df.empty:
            n = int((research_df["ticker"] == ticker).sum())
            heat = float(min(100.0, n * 10.0))

        composite = 0.4 * new_listing + 0.4 * liq + 0.2 * heat
        rows.append({
            "ticker": ticker,
            "leg": leg,
            "cohort": "newcomer" if new_listing > 0 else "core",
            "new_listing_score": round(new_listing, 1),
            "liquidity_score": round(liq, 1),
            "heat_score": round(heat, 1),
            "entrant_score": round(composite, 1),
        })
    return pd.DataFrame(rows)


# ── Rotation plan ────────────────────────────────────────────────────────────

def build_rotation_plan(
    inactive: pd.DataFrame,
    entrants: pd.DataFrame,
    max_per_leg: int = POOL_ROTATION_MAX,
) -> dict:
    """Pair the worst inactive names with the best entrants, per leg and
    cohort (core→core, newcomer→newcomer) so the 45+5 structure is preserved.

    Returns {"leg": {"out": [ticker...], "in": [ticker...]}}; both lists are
    the same length (1:1 swap). A leg with no candidates yields empty lists.
    """
    plan: dict = {}
    for leg in ("US", "China"):
        leg_out = inactive[inactive["leg"] == leg].sort_values(
            "inactivity_score", ascending=False
        )
        leg_in = entrants[entrants["leg"] == leg].sort_values(
            "entrant_score", ascending=False
        )
        outs: list[str] = []
        ins: list[str] = []
        for cohort in ("core", "newcomer"):
            cohort_out = leg_out[leg_out["cohort"] == cohort].head(max_per_leg)
            cohort_in = leg_in[leg_in["cohort"] == cohort].head(max_per_leg)
            n = min(len(cohort_out), len(cohort_in))
            outs.extend(cohort_out["ticker"].tolist()[:n])
            ins.extend(cohort_in["ticker"].tolist()[:n])
        plan[leg] = {"out": outs, "in": ins}
    return plan


def apply_rotation(
    universe_path: Path,
    plan: dict,
    new_pool_id: str,
    entrants: pd.DataFrame | None = None,
) -> list[dict]:
    """Apply a rotation plan to universe.yaml and return the changed entries.

    Outgoing names get ``pool: null, cohort: watch``; incoming names get
    ``pool: <new_pool_id>`` with the cohort taken from ``entrants``
    (newcomer for new listings, core otherwise). Every *retained* member is
    re-stamped onto ``new_pool_id`` too — the pool id names the whole roster
    for that quarter, so leaving the ~47 untouched names on the previous id
    would split the roster into two pools and make ``pool_membership`` for the
    new quarter contain only the handful of swapped-in names. The file's
    leading comment header is preserved.

    Only the ``changed`` entries (in/out) are returned; re-stamped retentions
    are not rotation events.
    """
    text = universe_path.read_text(encoding="utf-8")
    sep = text.find("- ticker:")
    header = text[:sep] if sep > 0 else ""
    data = yaml.safe_load(text)

    entrant_cohort = {}
    if entrants is not None and not entrants.empty:
        entrant_cohort = dict(zip(entrants["ticker"], entrants["cohort"], strict=False))

    changed: list[dict] = []
    by_ticker = {str(e["ticker"]): e for e in data}
    for leg, pair in plan.items():
        for ticker in pair["out"]:
            if ticker not in by_ticker:
                log.warning("rotation: %s not in universe — skipped", ticker)
                continue
            by_ticker[ticker]["pool"] = None
            by_ticker[ticker]["cohort"] = "watch"
            changed.append({"ticker": ticker, "leg": leg, "direction": "out"})
        for ticker in pair["in"]:
            if ticker not in by_ticker:
                log.warning("rotation: %s not in universe — skipped", ticker)
                continue
            by_ticker[ticker]["pool"] = new_pool_id
            by_ticker[ticker]["cohort"] = entrant_cohort.get(ticker, "core")
            changed.append({"ticker": ticker, "leg": leg, "direction": "in"})

    # Carry retained members onto the new pool id. Outgoing names were set to
    # None above, so every remaining non-null pool is a member of the roster.
    for entry in data:
        if entry.get("pool"):
            entry["pool"] = new_pool_id

    payload = header + "\n" + yaml.safe_dump(
        data, sort_keys=False, allow_unicode=True, default_flow_style=False
    )
    universe_path.write_text(payload, encoding="utf-8")
    return changed


# ── Rotation report ──────────────────────────────────────────────────────────

def generate_rotation_report(
    plan: dict,
    inactive: pd.DataFrame,
    entrants: pd.DataFrame,
    as_of: date,
    pool_id: str,
) -> str:
    """Human-readable markdown report for one rotation."""
    lines = [
        f"# ARF 季度组合轮换报告 — {as_of}",
        "",
        f"**目标池：** {pool_id}  |  **轮换上限：** 每腿每队列 ≤ {POOL_ROTATION_MAX} 只",
        "",
        "## 换出（最不活跃）",
        "",
    ]
    inact_idx = inactive.set_index("ticker") if not inactive.empty else pd.DataFrame()
    for leg in ("US", "China"):
        outs = plan.get(leg, {}).get("out", [])
        if not outs:
            lines += [f"### {leg} — 无换出", ""]
            continue
        lines += [f"### {leg} — 换出 {len(outs)} 只", ""]
        lines += ["| Ticker | 综合 | 流动性 | 数据质量 | 量能萎缩 | 惰性 |", "| --- | --- | --- | --- | --- | --- |"]
        for t in outs:
            r = inact_idx.loc[t] if t in inact_idx.index else {}
            lines.append(
                f"| {t} | {r.get('inactivity_score', '—')} | "
                f"{r.get('liquidity_score', '—')} | {r.get('quality_score', '—')} | "
                f"{r.get('fade_score', '—')} | {r.get('inertia_score', '—')} |"
            )
        lines.append("")

    lines += ["## 换入（更令人兴奋）", ""]
    ent_idx = entrants.set_index("ticker") if not entrants.empty else pd.DataFrame()
    for leg in ("US", "China"):
        ins = plan.get(leg, {}).get("in", [])
        if not ins:
            lines += [f"### {leg} — 无换入", ""]
            continue
        lines += [f"### {leg} — 换入 {len(ins)} 只", ""]
        lines += ["| Ticker | 综合 | 新上市 | 流动性 | 热度 |", "| --- | --- | --- | --- | --- |"]
        for t in ins:
            r = ent_idx.loc[t] if t in ent_idx.index else {}
            lines.append(
                f"| {t} | {r.get('entrant_score', '—')} | "
                f"{r.get('new_listing_score', '—')} | {r.get('liquidity_score', '—')} | "
                f"{r.get('heat_score', '—')} |"
            )
        lines.append("")

    lines += [
        "## 说明",
        "",
        "- 换出/换入按同队列 1:1 配对（core→core、newcomer→newcomer），保持每腿 45 核心 + 5 新秀结构。",
        "- 综合分 = 0.4×流动性 + 0.3×数据质量 + 0.2×量能萎缩 + 0.1×惰性（换出）；",
        "  0.4×新上市 + 0.4×流动性 + 0.2×热度（换入）。数据缺失的维度按 50 分中性处理。",
        "- 轮换已自动应用到 universe.yaml，成员快照已归档至 pool_membership，明细记录在 pool_changes。",
        "",
    ]
    return "\n".join(lines)


# ── End-to-end orchestration ─────────────────────────────────────────────────

def next_quarter_id(d: date) -> str:
    """Next quarter id after ``d``, e.g. 2026-08-09 → '2026Q4'."""
    q = (d.month - 1) // 3 + 1
    if q == 4:
        return f"{d.year + 1}Q1"
    return f"{d.year}Q{q + 1}"


def rotate_pool(
    conn,
    universe_path: Path = Path("config/universe.yaml"),
    as_of: date | None = None,
    new_pool_id: str | None = None,
    report_dir: Path = Path("reports"),
) -> dict:
    """Run one quarterly rotation end-to-end and return a summary.

    Pipeline: load universe → assemble snapshot/prices/research frames from
    DuckDB → score inactivity + entrants → build plan → apply to
    universe.yaml → archive membership + changes → write rotation report.

    ``new_pool_id`` defaults to the quarter after ``as_of`` (which defaults to
    today). Failures are logged, never fatal: the rotation is advisory in the
    sense that a broken score simply excludes that name.
    """
    import duckdb

    from arf.config import load_universe
    from arf.db import (
        query_pool_changes,  # noqa: F401  (import check in tests)
        upsert_pool_changes,
        upsert_pool_membership,
    )

    as_of = as_of or date.today()
    new_pool_id = new_pool_id or next_quarter_id(as_of)

    universe = load_universe(universe_path)
    cohort_map = {e.ticker: e.cohort for e in universe}

    snapshot_df = conn.execute("SELECT * FROM snapshots").fetchdf()
    prices_df = conn.execute(
        "SELECT ticker, date, close, volume FROM daily_prices ORDER BY ticker, date"
    ).fetchdf()
    try:
        research_df = conn.execute(
            "SELECT ticker FROM research_reports"
        ).fetchdf()
    except duckdb.Error:
        research_df = None

    if not snapshot_df.empty and "cohort" not in snapshot_df.columns:
        snapshot_df["cohort"] = snapshot_df["ticker"].map(cohort_map)

    inactive = inactivity_scores(snapshot_df, prices_df)
    watch = [
        e for e in universe
        if e.cohort == "watch" and e.leg in ("US", "China") and e.pool is None
    ]
    entrants = entrant_scores(watch, prices_df, research_df, as_of)

    for leg in ("US", "China"):
        if not any(e.leg == leg for e in watch):
            log.warning(
                "Rotation: no watchlist candidates for the %s leg — it cannot "
                "rotate. Add `cohort: watch` entries to %s.",
                leg, universe_path,
            )

    plan = build_rotation_plan(inactive, entrants)
    changed = apply_rotation(universe_path, plan, new_pool_id, entrants)

    # Archive the new membership (re-read the file so it is authoritative).
    new_universe = load_universe(universe_path)
    new_cohorts = {e.ticker: e.cohort for e in new_universe}
    membership = [
        {
            "ticker": e.ticker,
            "leg": e.leg,
            "cohort": e.cohort,
            "listed_at": e.listed_at,
            "reason": "quarterly rotation",
        }
        for e in new_universe
        if e.pool == new_pool_id
    ]
    upsert_pool_membership(conn, new_pool_id, membership)

    changes = [
        {
            "ticker": c["ticker"],
            "direction": c["direction"],
            # Post-rotation cohort: an incoming name's cohort is assigned by
            # apply_rotation, so the pre-rotation map would record "watch".
            "cohort": new_cohorts.get(c["ticker"], cohort_map.get(c["ticker"])),
            "reason": "rotation",
        }
        for c in changed
    ]
    upsert_pool_changes(conn, new_pool_id, changes)

    report = generate_rotation_report(
        plan, inactive, entrants, as_of=as_of, pool_id=new_pool_id
    )
    report_dir.mkdir(parents=True, exist_ok=True)
    out_path = report_dir / f"rotation_{new_pool_id}.md"
    out_path.write_text(report, encoding="utf-8")

    n_out = sum(len(pair["out"]) for pair in plan.values())
    n_in = sum(len(pair["in"]) for pair in plan.values())
    summary = {
        "pool": new_pool_id,
        "as_of": as_of.isoformat(),
        "swapped_out": n_out,
        "swapped_in": n_in,
        "report": str(out_path),
        "plan": plan,
    }
    log.info("Rotation %s: %d out / %d in", new_pool_id, n_out, n_in)
    return summary


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="ARF quarterly pool rotation")
    parser.add_argument("--rotate", action="store_true", help="Run the rotation")
    parser.add_argument("--as-of", type=date.fromisoformat, default=None,
                        help="Rotation date (default today)")
    parser.add_argument("--pool", default=None, help="New pool id (default next quarter)")
    parser.add_argument("--db", type=Path, default=Path("data/arf.db"))
    parser.add_argument("--universe", type=Path, default=Path("config/universe.yaml"))
    parser.add_argument("--report-dir", type=Path, default=Path("reports"))
    args = parser.parse_args()

    if not args.rotate:
        parser.print_help()
        return

    from arf.db import init_db

    conn = init_db(args.db)
    try:
        summary = rotate_pool(
            conn,
            universe_path=args.universe,
            as_of=args.as_of,
            new_pool_id=args.pool,
            report_dir=args.report_dir,
        )
        print(
            f"Rotation {summary['pool']}: "
            f"{summary['swapped_out']} out / {summary['swapped_in']} in — "
            f"report at {summary['report']}"
        )
    finally:
        conn.close()


if __name__ == "__main__":
    main()
