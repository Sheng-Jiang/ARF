"""ARF pipeline entry point.

Usage:
    python -m arf.run --as-of 2026-05-28
"""
import argparse
import logging
import os
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import UTC, date, datetime
from pathlib import Path

import pandas as pd
from rich.console import Console

from arf import storage
from arf.config import UniverseEntry, load_universe
from arf.db import (
    finish_run,
    init_db,
    query_thermometer_series,
    record_fetch_outcomes,
    start_run,
    upsert_snapshot,
)
from arf.fetchers.base import StockData
from arf.fetchers.china import fetch_china
from arf.fetchers.us import fetch_us
from arf.reporting import write_report
from arf.scoring import compute_arf

log = logging.getLogger(__name__)
console = Console()


def _stock_data_to_dict(sd: StockData) -> dict:
    return {
        "ticker": sd.ticker,
        "as_of_date": sd.as_of_date,
        "price": sd.price,
        "market_cap_usd": sd.market_cap_usd,
        "ev_usd": sd.ev_usd,
        "revenue_ttm": sd.revenue_ttm,
        "revenue_yoy_growth": sd.revenue_yoy_growth,
        "gross_margin": sd.gross_margin,
        "roe": sd.roe,
        "free_cash_flow": sd.free_cash_flow,
        "net_income_excl_nr": sd.net_income_excl_nonrecurring,
        "forward_pe": sd.forward_pe,
        "eps_2yr_cagr": sd.eps_2yr_cagr,
        "revenue_3yr_cagr": sd.revenue_3yr_cagr,
        "ps_ratio": sd.ps_ratio,
        "ev_sales": sd.ev_sales,
        "ev_sales_5yr_percentile": sd.ev_sales_5yr_percentile,
        "currency": sd.currency,
        "fx_rate_usd": sd.fx_rate_usd,
        "data_source": sd.data_source,
    }


def _fetch_one(entry: UniverseEntry, as_of: date) -> StockData:
    """Fetch a single ticker; return a null StockData on failure."""
    try:
        if entry.leg == "US":
            return fetch_us(entry, as_of)
        elif entry.leg == "China":
            return fetch_china(entry, as_of)
        else:
            # Pre-IPO and Europe-ref: return null data
            return StockData(ticker=entry.ticker, as_of_date=as_of,
                             data_source="manual")
    except Exception as exc:
        log.warning("Fetch failed for %s: %s — row will have null market data", entry.ticker, exc)
        return StockData(ticker=entry.ticker, as_of_date=as_of, data_source="error")


def fetch_all(universe: list[UniverseEntry], as_of: date) -> list[StockData]:
    results: list[StockData] = []
    with ThreadPoolExecutor(max_workers=8) as pool:
        futures = {pool.submit(_fetch_one, entry, as_of): entry for entry in universe}
        for future in as_completed(futures):
            entry = futures[future]
            try:
                results.append(future.result())
            except Exception as exc:
                log.warning("Unexpected error for %s: %s", entry.ticker, exc)
                results.append(StockData(ticker=entry.ticker, as_of_date=as_of))
    return results


def _build_scoring_df(
    stocks: list[StockData],
    universe: list[UniverseEntry],
) -> pd.DataFrame:
    entry_map = {e.ticker: e for e in universe}
    rows = []
    for sd in stocks:
        d = _stock_data_to_dict(sd)
        e = entry_map.get(sd.ticker)
        if e:
            d["leg"] = e.leg
            d["layer"] = e.layer
            d["name"] = e.name
            d["pure_play_pct"] = e.pure_play_pct
            d["policy_premium"] = e.policy_premium
        else:
            d["leg"] = "Unknown"
            d["layer"] = None
            d["name"] = sd.ticker
            d["pure_play_pct"] = 0.0
            d["policy_premium"] = False
        # Alias revenue_yoy_growth as revenue_ntm_growth for e_score
        d["revenue_ntm_growth"] = d.get("revenue_yoy_growth")
        rows.append(d)
    return pd.DataFrame(rows)


def _maybe_generate_gemini_summaries(
    conn,
    df: pd.DataFrame,
    as_of: date,
) -> None:
    """Generate Ask-Gemini per-stock summaries and persist them.

    No-op if GEMINI_API_KEY is unset. Failures here MUST NOT fail the pipeline —
    Gemini summarisation is a value-add layer on top of the numerical snapshot.
    """
    if not os.getenv("GEMINI_API_KEY"):
        log.info("GEMINI_API_KEY not set — skipping Gemini summarisation")
        return

    try:
        # webapp is included in the same package install for the cloud job.
        # If the import fails (e.g. running in a slim env), skip gracefully.
        from arf.db import upsert_gemini_summaries
        from webapp import gemini
    except ImportError as exc:
        log.warning("Gemini imports unavailable, skipping summarisation: %s", exc)
        return

    scored = df[df["leg"].isin(["US", "China"])]
    cohort = gemini.cohort_for_overview(scored)
    if not cohort:
        log.info("Empty cohort — skipping Gemini summarisation")
        return

    console.print(
        f"Generating Gemini summaries for {len(cohort)} stocks "
        f"(cohort_key={gemini.OVERVIEW_COHORT_KEY})…"
    )
    try:
        report = gemini.summarize_stocks(scored, cohort, as_of)
    except Exception:
        log.exception("Gemini summarisation failed — continuing pipeline")
        return

    generated_at = datetime.now(UTC).replace(tzinfo=None)
    rows = [
        gemini.summary_to_db_row(
            s, as_of, gemini.OVERVIEW_COHORT_KEY, report.model, generated_at,
        )
        for s in report.stocks
    ]
    upsert_gemini_summaries(conn, rows, as_of, gemini.OVERVIEW_COHORT_KEY)
    console.print(
        f"Persisted {len(rows)} Gemini cards "
        f"({sum(len(s.domain_mentions) for s in report.stocks)} domain mentions, "
        f"{len(report.citations)} grounded citations)"
    )


def _outcome_for(sd: StockData) -> str:
    if sd.data_source == "error":
        return "error"
    if sd.data_source == "manual":
        # Pre-IPO and Europe-ref entries — no market fetch attempted.
        return "skipped"
    if sd.price is None:
        return "partial"
    return "ok"


def fetch_daily_prices_yf(ticker: str, start_date: str, end_date: str) -> pd.DataFrame:
    """Fetch daily price history from yfinance and format it for DuckDB."""
    import yfinance as yf
    try:
        t = yf.Ticker(ticker)
        # Fetch history. yfinance expects YYYY-MM-DD strings for start and end
        hist = t.history(start=start_date, end=end_date, interval="1d")
        if hist.empty:
            log.warning("No daily prices returned from yfinance for %s", ticker)
            return pd.DataFrame()
            
        df = hist.reset_index()
        df["ticker"] = ticker
        df = df.rename(columns={
            "Date": "date",
            "Open": "open",
            "High": "high",
            "Low": "low",
            "Close": "close",
            "Volume": "volume"
        })
        # yfinance Date column might be timezone-aware; normalize to naive date
        df["date"] = pd.to_datetime(df["date"]).dt.date
        df = df[["ticker", "date", "open", "high", "low", "close", "volume"]]
        
        for col in ["open", "high", "low", "close", "volume"]:
            df[col] = pd.to_numeric(df[col], errors="coerce")
            
        return df
    except Exception as e:
        log.warning("Failed to fetch daily prices from yfinance for %s: %s", ticker, e)
        return pd.DataFrame()


def _run_technical_pipeline(conn, df: pd.DataFrame, universe: list[UniverseEntry], as_of: date) -> None:
    """Pre-calculate and cache daily prices and technical metrics for scored universe stocks in DuckDB.
    
    This ensures that the AI-Screener and dashboard charts have pre-populated data out-of-the-box.
    """
    from arf.fetchers.akshare import fetch_daily_prices
    from arf.technical import calculate_technical_indicators, calculate_chip_distribution, score_stock_technical
    from arf.db import upsert_daily_prices, upsert_technical_metrics
    from datetime import timedelta
    import numpy as np
    
    scored_stocks = [e for e in universe if e.leg in ("US", "China")]
    if not scored_stocks:
        return
        
    console.print(f"Running technical pipeline for {len(scored_stocks)} scored universe stocks...")
    tech_rows = []
    
    # Estimate outstanding shares for each stock from the fundamental snapshot
    # outstanding_shares = (market_cap_usd * fx_rate_usd) / price
    shares_map = {}
    for _, r in df.iterrows():
        ticker = r["ticker"]
        mc_usd = r.get("market_cap_usd")
        fx = r.get("fx_rate_usd", 1.0)  # Default to 1.0 (e.g., US stocks)
        price = r.get("price")
        if mc_usd and price:
            shares = (mc_usd * fx) / price
            # Adjust scaling if needed (A-shares might need scaling, but keep it generic)
            if shares < 1_000_000:
                shares *= 1_000_000
            shares_map[ticker] = shares
            
    # 250 calendar days lookback to calculate moving averages and chip decay accurately
    start_date = as_of - timedelta(days=250)
    start_str = start_date.strftime("%Y-%m-%d")
    end_str = as_of.strftime("%Y-%m-%d")
    
    for entry in scored_stocks:
        ticker = entry.ticker
        try:
            # 1. Fetch daily prices (A-shares from AkShare, others from yfinance)
            if entry.leg == "China" and (ticker.endswith(".SZ") or ticker.endswith(".SH")):
                prices_df = fetch_daily_prices(ticker, start_str, end_str, adjust="qfq")
                is_a_share = True
            else:
                prices_df = fetch_daily_prices_yf(ticker, start_str, end_str)
                is_a_share = False
                
            if prices_df.empty:
                log.warning("No daily prices returned for %s in technical pipeline", ticker)
                continue
                
            # 2. Save daily prices
            upsert_daily_prices(conn, prices_df)
            
            # 3. Calculate indicators
            ind_df = calculate_technical_indicators(prices_df)
            if ind_df.empty:
                continue
                
            # 4. Calculate chips
            shares = shares_map.get(ticker, 100_000_000.0)
            chip_metrics = calculate_chip_distribution(prices_df, shares, is_a_share=is_a_share)
            profit_ratio, avg_cost, c90_min, c90_max, c70_min, c70_max = chip_metrics
            
            # 5. Score technical
            latest = ind_df.iloc[-1]
            score = score_stock_technical(latest, chip_metrics)
            
            tech_rows.append({
                "ticker": ticker,
                "technical_score": score,
                "ma5": latest.get("ma5"),
                "ma10": latest.get("ma10"),
                "ma20": latest.get("ma20"),
                "ma30": latest.get("ma30"),
                "ma60": latest.get("ma60"),
                "ma120": latest.get("ma120"),
                "ma_bullish_alignment": bool(latest.get("ma_bullish_alignment", False)),
                "macd_dif": latest.get("macd_dif"),
                "macd_dea": latest.get("macd_dea"),
                "macd_hist": latest.get("macd_hist"),
                "rsi": latest.get("rsi"),
                "bollinger_mid": latest.get("bollinger_mid"),
                "bollinger_upper": latest.get("bollinger_upper"),
                "bollinger_lower": latest.get("bollinger_lower"),
                "atr": latest.get("atr"),
                "chip_profit_ratio": profit_ratio,
                "chip_avg_cost": avg_cost,
                "chip_90_cost_min": c90_min,
                "chip_90_cost_max": c90_max,
                "chip_70_cost_min": c70_min,
                "chip_70_cost_max": c70_max
            })
        except Exception as e:
            log.warning("Technical pipeline failed for %s: %s", ticker, e)
            
    if tech_rows:
        tech_df = pd.DataFrame(tech_rows)
        upsert_technical_metrics(conn, tech_df, as_of)
        console.print(f"Cached technical and chip metrics for {len(tech_rows)} stocks in DuckDB")


def run_pipeline(
    as_of: date,
    data_dir: Path = Path("data"),
    report_dir: Path = Path("reports"),
    universe_path: Path = Path("config/universe.yaml"),
    trigger_source: str = "manual",
) -> pd.DataFrame:
    """Run the full ARF pipeline for a given as-of date.

    If env OUTPUT_TARGET=gcs, downloads the existing arf.db from
    `gs://$GCS_BUCKET/$GCS_DB_OBJECT` before running, and uploads the updated DB
    plus the snapshot parquet + markdown report when finished.
    """
    console.print(f"[bold]ARF pipeline[/bold] — as of {as_of} (trigger: {trigger_source})")

    db_path = data_dir / "arf.db"
    if storage.is_gcs_mode():
        storage.download_db_if_present(db_path)

    universe = load_universe(universe_path)
    console.print(f"Loaded {len(universe)} universe entries")

    conn = init_db(db_path)
    run_id = uuid.uuid4().hex
    start_run(conn, run_id=run_id, as_of_date=as_of, trigger_source=trigger_source)

    try:
        console.print("Fetching market data…")
        stocks = fetch_all(universe, as_of)
        outcomes = [(s.ticker, _outcome_for(s), s.data_source or None) for s in stocks]
        ok = sum(1 for _, st, _ in outcomes if st == "ok")
        failed = sum(1 for _, st, _ in outcomes if st == "error")
        console.print(
            f"Fetched {len(stocks)} stocks "
            f"({sum(1 for s in stocks if s.price is not None)} with price data)"
        )

        df = _build_scoring_df(stocks, universe)
        df = compute_arf(df)

        upsert_snapshot(conn, df, as_of)
        record_fetch_outcomes(conn, run_id, outcomes)
        console.print(f"Snapshot saved to {db_path}")

        # Pre-calculate and cache technical indicators for A-shares
        try:
            _run_technical_pipeline(conn, df, universe, as_of)
        except Exception as e:
            log.exception("Technical indicators cache failed - continuing main pipeline")

        _maybe_generate_gemini_summaries(conn, df, as_of)

        # Write parquet
        snap_dir = data_dir / "snapshots"
        snap_dir.mkdir(parents=True, exist_ok=True)
        parquet_path = snap_dir / f"arf_{as_of}.parquet"
        df.to_parquet(parquet_path, index=False)
        console.print(f"Parquet written: {parquet_path}")

        # Render reports
        thermo = query_thermometer_series(conn)
        write_report(df, thermo, as_of, report_dir)
        console.print(f"Reports written to {report_dir}/")

        status = "partial" if failed > 0 else "success"
        finish_run(
            conn, run_id=run_id, status=status,
            tickers_total=len(stocks), tickers_ok=ok, tickers_failed=failed,
        )
        conn.close()

        if storage.is_gcs_mode():
            storage.upload_db(db_path)
            storage.upload_artifact(parquet_path, f"snapshots/arf_{as_of}.parquet")
            md_path = report_dir / f"arf_{as_of}.md"
            if md_path.exists():
                storage.upload_artifact(md_path, f"reports/arf_{as_of}.md")
            thermo_html = report_dir / "thermometer.html"
            if thermo_html.exists():
                storage.upload_artifact(thermo_html, "reports/thermometer.html")
            console.print("Synced artifacts to GCS")

        _print_calibration_summary(df)
        return df
    except Exception as exc:
        log.exception("Pipeline failed")
        finish_run(
            conn, run_id=run_id, status="error",
            tickers_total=0, tickers_ok=0, tickers_failed=0,
            error_message=str(exc),
        )
        conn.close()
        if storage.is_gcs_mode():
            # Persist the run-failure record so the webapp can show it.
            try:
                storage.upload_db(db_path)
            except Exception:
                log.exception("Failed to upload DB after pipeline failure")
        raise


def _print_calibration_summary(df: pd.DataFrame) -> None:
    console.print("\n[bold]Calibration check[/bold]")
    targets = {
        "NVDA": "D2–D4 (high E, not bubbly)",
        "PLTR": "D1 (US froth flag)",
        "CSCO": "D6–D10 (low AI, not bubbly)",
        "688256.SH": "D1 China (Cambricon froth)",
    }
    scored = df[df["arf"].notna()]
    for ticker, expectation in targets.items():
        row = scored[scored["ticker"] == ticker]
        if row.empty:
            console.print(f"  {ticker}: [yellow]not found[/yellow]")
        else:
            r = row.iloc[0]
            froth = "★" if r.get("froth_flag") else ""
            console.print(
                f"  {ticker}: D{r['decile']} ARF={r['arf']:.1f} "
                f"E={r['e_score']:.1f} V={r['v_score']:.1f} {froth}  "
                f"(expected: {expectation})"
            )


def main() -> None:
    logging.basicConfig(level=logging.WARNING, format="%(levelname)s %(name)s: %(message)s")
    parser = argparse.ArgumentParser(description="Run the ARF pipeline")
    parser.add_argument("--as-of", required=False, type=date.fromisoformat,
                        default=None,
                        help="Snapshot date (YYYY-MM-DD). Defaults to env AS_OF or today UTC.")
    parser.add_argument("--data-dir", type=Path, default=Path("data"))
    parser.add_argument("--report-dir", type=Path, default=Path("reports"))
    parser.add_argument("--universe", type=Path, default=Path("config/universe.yaml"))
    parser.add_argument("--trigger-source", default=os.getenv("TRIGGER_SOURCE", "manual"),
                        help="Tag for the run record: manual|scheduler|webapp")
    args = parser.parse_args()

    as_of = args.as_of
    if as_of is None:
        env_date = os.getenv("AS_OF")
        as_of = date.fromisoformat(env_date) if env_date else date.today()

    run_pipeline(
        as_of=as_of,
        data_dir=args.data_dir,
        report_dir=args.report_dir,
        universe_path=args.universe,
        trigger_source=args.trigger_source,
    )


if __name__ == "__main__":
    main()
