"""Pipeline health: freshness, field coverage, and calibration bands.

Used by the batch job (console summary) and the webapp (admin / sidebar).
All functions are pure / read-only over DataFrames or simple scalars.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import Literal

import pandas as pd

# ── Freshness ────────────────────────────────────────────────────────────────

# Weekly Monday cadence: green through weekend after the run; yellow mid-week
# after a missed Monday; red once two Mondays have passed without a snapshot.
FRESH_DAYS = 7
STALE_DAYS = 10

FreshLevel = Literal["fresh", "stale", "critical", "unknown"]


@dataclass(frozen=True)
class FreshnessStatus:
    level: FreshLevel
    latest_as_of: date | None
    age_days: int | None
    label: str
    detail: str


def freshness_status(
    latest_as_of: date | None,
    *,
    today: date | None = None,
    fresh_days: int = FRESH_DAYS,
    stale_days: int = STALE_DAYS,
) -> FreshnessStatus:
    """Classify how current the latest snapshot is vs. a weekly cadence."""
    today = today or date.today()
    if latest_as_of is None:
        return FreshnessStatus(
            level="unknown",
            latest_as_of=None,
            age_days=None,
            label="无快照",
            detail="数据库中没有任何 ARF 快照。请先运行管道。",
        )
    age = (today - latest_as_of).days
    if age < 0:
        # Future-dated snapshot (timezone / clock skew) — treat as fresh.
        return FreshnessStatus(
            level="fresh",
            latest_as_of=latest_as_of,
            age_days=age,
            label="数据新鲜",
            detail=f"最新快照 {latest_as_of}（日期在未来，可能是时区问题）。",
        )
    if age <= fresh_days:
        return FreshnessStatus(
            level="fresh",
            latest_as_of=latest_as_of,
            age_days=age,
            label="数据新鲜",
            detail=f"最新快照 {latest_as_of}，距今 {age} 天（周更节奏内）。",
        )
    if age <= stale_days:
        return FreshnessStatus(
            level="stale",
            latest_as_of=latest_as_of,
            age_days=age,
            label="数据偏旧",
            detail=(
                f"最新快照 {latest_as_of}，距今 {age} 天。"
                f"超过周更窗口（>{fresh_days}d），请确认调度器是否已跑。"
            ),
        )
    return FreshnessStatus(
        level="critical",
        latest_as_of=latest_as_of,
        age_days=age,
        label="数据过期",
        detail=(
            f"最新快照 {latest_as_of}，距今 {age} 天。"
            f"已超过两周节奏（>{stale_days}d）——排名不可信，请立即触发管道。"
        ),
    )


# ── Field coverage ───────────────────────────────────────────────────────────

# Inputs that drive E_score / V_score. Pure-play % and layer come from YAML
# (always present), so they are not listed.
_E_FIELDS = ("gross_margin", "revenue_yoy_growth")
_V_FIELDS = (
    "free_cash_flow",
    "forward_pe",
    "eps_2yr_cagr",
    "ev_sales_5yr_percentile",
)
_CORE_FIELDS = ("price", "roe", "ps_ratio", "e_score", "v_score", "arf")

# Human-readable labels for the admin UI
FIELD_LABELS: dict[str, str] = {
    "price": "价格",
    "gross_margin": "毛利率 (E)",
    "revenue_yoy_growth": "营收增速 (E)",
    "free_cash_flow": "FCF (V-C1)",
    "forward_pe": "预期P/E (V-C2)",
    "eps_2yr_cagr": "EPS CAGR (V-C2)",
    "ev_sales_5yr_percentile": "EV/S五年分位 (V-C3)",
    "roe": "ROE",
    "ps_ratio": "P/S",
    "e_score": "E分",
    "v_score": "V分",
    "arf": "ARF",
}


@dataclass(frozen=True)
class FieldCoverage:
    field: str
    present: int
    total: int

    @property
    def rate(self) -> float:
        return self.present / self.total if self.total else 0.0

    @property
    def pct(self) -> int:
        return int(round(self.rate * 100))


@dataclass(frozen=True)
class LegCoverage:
    leg: str
    n_tickers: int
    n_scored: int  # arf not null
    fields: dict[str, FieldCoverage]
    # Approximate V-component reconstructability (same rules as scoring.py)
    v_c1_usable: int  # FCF present and >= 0, market_cap present
    v_c2_usable: int  # forward_pe + positive eps_2yr_cagr
    v_c3_usable: int  # ev_sales_5yr_percentile present

    @property
    def scored_rate(self) -> float:
        return self.n_scored / self.n_tickers if self.n_tickers else 0.0


@dataclass(frozen=True)
class CoverageReport:
    as_of: date | None
    legs: dict[str, LegCoverage]
    warnings: list[str] = field(default_factory=list)

    @property
    def overall_ok(self) -> bool:
        return len(self.warnings) == 0


def _count_present(s: pd.Series) -> int:
    return int(s.notna().sum())


def _leg_coverage(leg: str, g: pd.DataFrame) -> LegCoverage:
    total = len(g)
    fields: dict[str, FieldCoverage] = {}
    for col in (*_CORE_FIELDS, *_E_FIELDS, *_V_FIELDS):
        if col not in g.columns:
            fields[col] = FieldCoverage(field=col, present=0, total=total)
            continue
        fields[col] = FieldCoverage(
            field=col, present=_count_present(g[col]), total=total
        )

    # Mirror scoring.py reverse_dcf / PEG gates
    if {"free_cash_flow", "market_cap_usd"}.issubset(g.columns):
        c1 = (
            g["free_cash_flow"].notna()
            & g["market_cap_usd"].notna()
            & (g["free_cash_flow"] >= 0)
        ).sum()
    else:
        c1 = 0
    if {"forward_pe", "eps_2yr_cagr"}.issubset(g.columns):
        c2 = (
            g["forward_pe"].notna()
            & g["eps_2yr_cagr"].notna()
            & (g["eps_2yr_cagr"] > 0)
        ).sum()
    else:
        c2 = 0
    c3 = (
        _count_present(g["ev_sales_5yr_percentile"])
        if "ev_sales_5yr_percentile" in g.columns
        else 0
    )

    n_scored = _count_present(g["arf"]) if "arf" in g.columns else 0
    return LegCoverage(
        leg=leg,
        n_tickers=total,
        n_scored=n_scored,
        fields=fields,
        v_c1_usable=int(c1),
        v_c2_usable=int(c2),
        v_c3_usable=int(c3),
    )


def _coverage_warnings(legs: dict[str, LegCoverage]) -> list[str]:
    """Flag systemic data holes that make ARF rankings less trustworthy."""
    warnings: list[str] = []
    for leg_name, leg in legs.items():
        if leg.n_tickers == 0:
            continue
        if leg.scored_rate < 0.9:
            warnings.append(
                f"{leg_name}: 仅 {leg.n_scored}/{leg.n_tickers} 只产出 ARF "
                f"({leg.scored_rate:.0%})，低于 90% 门槛"
            )
        # V-C1 reverse-DCF is the most economically meaningful stretch signal
        if leg.v_c1_usable / leg.n_tickers < 0.5:
            warnings.append(
                f"{leg_name}: 逆向DCF可用仅 {leg.v_c1_usable}/{leg.n_tickers} "
                f"({leg.v_c1_usable / leg.n_tickers:.0%}) — V分主要靠 PEG/EV·S 撑着"
            )
        rev = leg.fields.get("revenue_yoy_growth")
        if rev is not None and rev.rate < 0.5:
            warnings.append(
                f"{leg_name}: 营收增速覆盖 {rev.present}/{rev.total} "
                f"({rev.pct}%) — E分增长项大量回落默认值"
            )
        c3 = leg.fields.get("ev_sales_5yr_percentile")
        if c3 is not None and c3.rate < 0.5:
            warnings.append(
                f"{leg_name}: EV/S 五年分位覆盖 {c3.present}/{c3.total} "
                f"({c3.pct}%) — V-C3 缺失"
            )
    return warnings


def coverage_report(df: pd.DataFrame, as_of: date | None = None) -> CoverageReport:
    """Compute field + V-component coverage for US/China legs in a snapshot."""
    if df.empty:
        return CoverageReport(as_of=as_of, legs={}, warnings=["快照为空"])

    if as_of is None and "as_of_date" in df.columns and df["as_of_date"].notna().any():
        raw = df["as_of_date"].iloc[0]
        as_of = raw.date() if isinstance(raw, datetime) else raw

    legs: dict[str, LegCoverage] = {}
    for leg_name in ("US", "China"):
        if "leg" not in df.columns:
            break
        g = df[df["leg"] == leg_name]
        if g.empty:
            continue
        legs[leg_name] = _leg_coverage(leg_name, g)

    return CoverageReport(
        as_of=as_of,
        legs=legs,
        warnings=_coverage_warnings(legs),
    )


def coverage_to_frame(report: CoverageReport) -> pd.DataFrame:
    """Flat table for Streamlit: one row per leg × field."""
    rows: list[dict] = []
    for leg in report.legs.values():
        for col, cov in leg.fields.items():
            rows.append({
                "leg": leg.leg,
                "field": col,
                "label": FIELD_LABELS.get(col, col),
                "present": cov.present,
                "total": cov.total,
                "pct": cov.pct,
            })
    return pd.DataFrame(rows)


# ── Calibration suite ────────────────────────────────────────────────────────

# Bands are inclusive deciles (1 = most stretched). Sourced from PRD §7 plus
# operational sanity checks observed in production (e.g. GOOGL should not be D1).
CALIBRATION_TARGETS: dict[str, tuple[int, int]] = {
    "NVDA": (2, 5),          # high E, strong ROE keeps V moderate (PRD D2–D4, allow D5)
    "PLTR": (1, 2),          # narrative stretch poster child
    "LITE": (1, 3),          # optical / AI infra froth
    "CSCO": (6, 10),         # mature networking, low AI pure-play
    "NEE": (6, 10),          # energy, low E
    "BIDU": (5, 10),         # China big-tech, not top froth (widened from PRD D6–10)
    "BABA": (6, 10),
    "0700.HK": (6, 10),      # Tencent
    "300394.SZ": (1, 3),     # 天孚 — optical froth
    "688256.SH": (1, 3),     # 寒武纪 — policy + narrative
    "GOOGL": (2, 8),         # quality mega-cap must not sit alone at D1 froth tier
    "PANW": (1, 3),          # security AI narrative, often froth-flagged
}


@dataclass(frozen=True)
class CalibrationResult:
    ticker: str
    expected_lo: int
    expected_hi: int
    decile: int | None
    arf: float | None
    e_score: float | None
    v_score: float | None
    froth_flag: bool
    status: Literal["pass", "fail", "missing"]

    @property
    def ok(self) -> bool:
        return self.status == "pass"


@dataclass(frozen=True)
class CalibrationReport:
    as_of: date | None
    results: list[CalibrationResult]

    @property
    def n_pass(self) -> int:
        return sum(1 for r in self.results if r.status == "pass")

    @property
    def n_fail(self) -> int:
        return sum(1 for r in self.results if r.status == "fail")

    @property
    def n_missing(self) -> int:
        return sum(1 for r in self.results if r.status == "missing")

    @property
    def overall_ok(self) -> bool:
        return self.n_fail == 0 and self.n_missing == 0


def _safe_float(v: object) -> float | None:
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return None
    try:
        f = float(v)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return None
    return None if pd.isna(f) else f


def _safe_int(v: object) -> int | None:
    f = _safe_float(v)
    return None if f is None else int(f)


def calibration_check(
    df: pd.DataFrame,
    targets: dict[str, tuple[int, int]] | None = None,
    as_of: date | None = None,
) -> CalibrationReport:
    """Check key tickers land in expected decile bands."""
    targets = targets or CALIBRATION_TARGETS
    if as_of is None and "as_of_date" in df.columns and not df.empty:
        raw = df["as_of_date"].iloc[0]
        as_of = raw.date() if isinstance(raw, datetime) else raw

    by_ticker = (
        df.drop_duplicates(subset=["ticker"], keep="last").set_index("ticker")
        if not df.empty and "ticker" in df.columns
        else pd.DataFrame()
    )

    results: list[CalibrationResult] = []
    for ticker, (lo, hi) in targets.items():
        if by_ticker.empty or ticker not in by_ticker.index:
            results.append(
                CalibrationResult(
                    ticker=ticker,
                    expected_lo=lo,
                    expected_hi=hi,
                    decile=None,
                    arf=None,
                    e_score=None,
                    v_score=None,
                    froth_flag=False,
                    status="missing",
                )
            )
            continue
        row = by_ticker.loc[ticker]
        # Handle rare duplicate index edge case
        if isinstance(row, pd.DataFrame):
            row = row.iloc[-1]
        decile = _safe_int(row.get("decile"))
        status: Literal["pass", "fail", "missing"]
        if decile is None:
            status = "missing"
        elif lo <= decile <= hi:
            status = "pass"
        else:
            status = "fail"
        results.append(
            CalibrationResult(
                ticker=ticker,
                expected_lo=lo,
                expected_hi=hi,
                decile=decile,
                arf=_safe_float(row.get("arf")),
                e_score=_safe_float(row.get("e_score")),
                v_score=_safe_float(row.get("v_score")),
                froth_flag=bool(row.get("froth_flag")),
                status=status,
            )
        )
    return CalibrationReport(as_of=as_of, results=results)


def calibration_to_frame(report: CalibrationReport) -> pd.DataFrame:
    rows = []
    for r in report.results:
        rows.append({
            "ticker": r.ticker,
            "decile": r.decile,
            "expected": f"D{r.expected_lo}–D{r.expected_hi}",
            "arf": r.arf,
            "e_score": r.e_score,
            "v_score": r.v_score,
            "froth": r.froth_flag,
            "status": r.status,
        })
    return pd.DataFrame(rows)


# ── Combined health snapshot ─────────────────────────────────────────────────

@dataclass(frozen=True)
class HealthSnapshot:
    freshness: FreshnessStatus
    coverage: CoverageReport
    calibration: CalibrationReport

    @property
    def level(self) -> FreshLevel:
        """Worst-of freshness / coverage / calibration for a single badge."""
        if self.freshness.level == "critical":
            return "critical"
        cal_broken = self.calibration.n_fail > 0 or self.calibration.n_missing > 0
        if cal_broken or not self.coverage.overall_ok:
            # Soft-fail: data is timely but rankings may not be trustworthy.
            if self.freshness.level == "fresh":
                return "stale"
            return self.freshness.level
        return self.freshness.level


def evaluate_health(
    df: pd.DataFrame,
    *,
    latest_as_of: date | None = None,
    today: date | None = None,
) -> HealthSnapshot:
    """One-shot health evaluation for a snapshot DataFrame."""
    if latest_as_of is None and "as_of_date" in df.columns and not df.empty:
        raw = df["as_of_date"].iloc[0]
        latest_as_of = raw.date() if isinstance(raw, datetime) else raw
    return HealthSnapshot(
        freshness=freshness_status(latest_as_of, today=today),
        coverage=coverage_report(df, as_of=latest_as_of),
        calibration=calibration_check(df, as_of=latest_as_of),
    )


def next_monday_utc(from_day: date | None = None) -> date:
    """Next scheduled Monday (inclusive if today is Monday)."""
    d = from_day or date.today()
    # Monday = 0
    days_ahead = (0 - d.weekday()) % 7
    return d + timedelta(days=days_ahead)
