"""Build the 50/50 quarterly pool universe (100 scored names) from scratch.

Migrations the legacy 86-entry universe.yaml into the quarterly-pool model:

- **US leg (50)**: 45 core (legacy 36 US + 8 Europe ADRs moved in + AMZN) +
  5 newcomers (all listed: CRWV/ALAB/NBIS/OKLO/SERV).
- **China leg (50)**: 45 core (legacy 37 minus Zhipu/MiniMax + 10 new) +
  5 newcomers (9660.HK/2513.HK/0100.HK/9880.HK/2533.HK).
- **Watchlist (pool=null)**: GEV/CRWD/SNOW/UBER — candidates for rotation.
- **Pre-IPO observation (pool=null)**: legacy 5 + SpaceX/CXMT/Unitree — display
  only, no scoring (static valuations live in config/value_chain.yaml).

Idempotent: re-running on an already-migrated file adds no duplicates and only
updates pool/cohort fields. Reuse for the next quarter by passing ``--pool``.

Usage:
    python scripts/build_pool_universe.py                 # pool 2026Q3
    python scripts/build_pool_universe.py --pool 2026Q4   # next quarter
"""
from __future__ import annotations

import argparse
from pathlib import Path

import yaml

POOL_ID = "2026Q3"

# ── Existing entries by role ─────────────────────────────────────────────────

# Legacy US 36 → core, pool
US_CORE_LEGACY = {
    "NVDA", "AMD", "INTC", "MSFT", "CRM", "EQIX", "DLR", "ANET", "CSCO",
    "NEE", "WMB", "COHR", "LITE", "AVGO", "MRVL", "PLTR", "TSM", "MU",
    "QCOM", "KLAC", "LRCX", "AMAT", "GOOGL", "META", "AAPL", "TSLA",
    "ORCL", "NOW", "DELL", "VRT", "CEG", "VST", "SMCI", "ADBE", "PANW",
    "SNPS",
}

# Legacy Europe-ref ADRs → moved into the US leg (yfinance-valid tickers).
EUROPE_TO_US = {
    "ASML": ("ASML", "ASML (ADR)"),
    "ARM": ("ARM", "Arm Holdings (ADR)"),
    "SMEGY": ("SMEGF", "Siemens Energy (OTC ADR)"),
    "SBGSF": ("SBGSF", "Schneider Electric (OTC ADR)"),
    "STM": ("STM", "STMicroelectronics (ADR)"),
    "IFNNY": ("IFNNY", "Infineon (ADR)"),
    "SAP": ("SAP", "SAP (ADR)"),
    "ABB": ("ABBNY", "ABB (OTC ADR)"),
}

# Legacy China 37: Zhipu + MiniMax move to newcomer; the rest stay core.
CHINA_NEWCOMER_LEGACY = {"2513.HK", "0100.HK"}
CHINA_CORE_LEGACY = {
    "300308.SZ", "300502.SZ", "300394.SZ", "688498.SH", "002281.SZ",
    "688256.SH", "688981.SH", "000977.SZ", "GDS", "VNET", "300750.SZ",
    "BIDU", "BABA", "0700.HK", "9868.HK", "601138.SH", "002463.SZ",
    "300496.SZ", "002230.SZ", "688111.SH", "1810.HK", "3690.HK",
    "002415.SZ", "300033.SZ", "688787.SH", "603501.SH", "603986.SH",
    "688012.SH", "0981.HK", "1347.HK", "600584.SH", "000063.SZ",
    "300017.SZ", "300151.SZ", "600268.SH",
}

# ── New entries: (name, leg, layer, pure_play, exchange, listed_at, notes) ───
# listed_at: used by the rotation logic for the "listed ≤ 12 months" signal.

US_ADD_CORE = {
    "AMZN": ("Amazon", "US", "L3", 25, "NASDAQ", "1997-05-15",
             "AWS AI 收入占比提升；其余为电商/广告"),
}

US_NEWCOMER = {
    "CRWV": ("CoreWeave", "US", "L3", 90, "NASDAQ", "2025-03-28",
             "AI 算力云新秀（GPU 云）"),
    "ALAB": ("Astera Labs", "US", "L2", 85, "NASDAQ", "2024-03-20",
             "AI 数据中心连接芯片新秀"),
    "NBIS": ("Nebius", "US", "L4", 80, "NASDAQ", "2024-10-21",
             "AI 云基础设施新秀"),
    "OKLO": ("Oklo", "US", "L1", 40, "NYSE", "2024-05-09",
             "先进核能 / AI 供电新秀"),
    "SERV": ("Serve Robotics", "US", "L5", 70, "NASDAQ", "2024-07-19",
             "物理 AI 送餐机器人新秀"),
}

US_WATCH = {
    "GEV": ("GE Vernova", "US", "L1", 30, "NYSE", "2024-04-02",
            "轮换候选：能源设备"),
    "CRWD": ("CrowdStrike", "US", "L5", 60, "NASDAQ", "2019-06-12",
             "轮换候选：安全 AI"),
    "SNOW": ("Snowflake", "US", "L4", 50, "NYSE", "2020-09-16",
             "轮换候选：数据云"),
    "UBER": ("Uber", "US", "L5", 30, "NYSE", "2019-05-10",
             "轮换候选：自动驾驶"),
}

# 每条腿都必须有轮换候选：build_rotation_plan 按 1:1 配对换出/换入，
# 候选为空的一条腿产出的永远是空计划，季度轮换对它彻底失效。
CHINA_WATCH = {
    "6682.HK": ("第四范式", "China", "L4", 90, "HKEX", "2023-09-28",
                "轮换候选：企业级 AI 平台（纯 AI 标的）"),
    "300474.SZ": ("景嘉微", "China", "L2", 55, "SZSE", "2016-03-15",
                  "轮换候选：国产 GPU"),
    "688521.SH": ("芯原股份", "China", "L2", 60, "SSE", "2020-08-18",
                  "轮换候选：芯片设计 IP / Chiplet"),
    "0992.HK": ("联想集团", "China", "L3", 30, "HKEX", "1994-02-14",
                "轮换候选：AI 服务器 / AI PC"),
}

CHINA_ADD_CORE = {
    "688041.SH": ("海光信息 Hygon", "China", "L2", 95, "SH", "2022-08-12",
                  "国产 CPU / DCU 加速卡"),
    "002371.SZ": ("北方华创 NAURA", "China", "L2", 70, "SZ", "2010-03-16",
                  "半导体设备龙头"),
    "688008.SH": ("澜起科技 Montage", "China", "L2", 75, "SH", "2019-07-08",
                  "内存接口芯片"),
    "688047.SH": ("龙芯中科 Loongson", "China", "L2", 60, "SH", "2022-06-24",
                  "国产 CPU"),
    "603019.SH": ("中科曙光 Sugon", "China", "L3", 80, "SH", "2014-11-06",
                  "高性能计算 / AI 服务器"),
    "000938.SZ": ("紫光股份 Unisplendour", "China", "L3", 50, "SZ", "1999-11-04",
                  "新华三 / 网络设备"),
    "002594.SZ": ("比亚迪 BYD", "China", "L5", 30, "SZ", "2011-06-30",
                  "新能源车 / 物理 AI"),
    "PDD": ("拼多多 PDD", "China", "L5", 20, "NASDAQ", "2018-07-26",
            "电商 AI 应用（中概 ADR）"),
    "1024.HK": ("快手 Kuaishou", "China", "L5", 40, "HK", "2021-02-05",
                "短视频 AI"),
    "0020.HK": ("商汤 SenseTime", "China", "L4", 70, "HK", "2021-12-30",
                "AI 视觉大模型"),
}

CHINA_NEWCOMER = {
    "9660.HK": ("地平线 Horizon Robotics", "China", "L2", 85, "HK", "2024-10-24",
                "智驾芯片新秀"),
    "2513.HK": ("智谱 Zhipu", "China", "L4", 100, "HK", "2026-01-01",
                "大模型新秀"),
    "0100.HK": ("MiniMax", "China", "L4", 100, "HK", "2026-01-01",
                "多模态大模型新秀"),
    "9880.HK": ("优必选 UBTech", "China", "L5", 75, "HK", "2023-12-29",
                "人形机器人新秀"),
    "2533.HK": ("黑芝麻 Black Sesame", "China", "L2", 80, "HK", "2024-08-08",
                "智驾 SoC 新秀"),
}

PREIPO_OBSERVE = {
    "SPACEX": ("SpaceX", "Pre-IPO", "L3", 0, "", None,
               "未上市观察（静态估值展示）"),
    "CXMT": ("长鑫存储 CXMT", "Pre-IPO", "L2", 0, "", None,
             "未上市观察（DRAM 新秀）"),
    "UNITREE": ("宇树 Unitree", "Pre-IPO", "L5", 0, "", None,
                "未上市观察（人形机器人新秀）"),
}

HEADER = """# ARF Seed Universe — quarterly 50/50 pool
# Generated by scripts/build_pool_universe.py — edit that script for the next
# quarter's roster, then re-run it. The full candidate universe (superset)
# lives here; entries with `pool: null` are watchlist / observation only.
#
# universe_version: "2026-06-26" — legacy pool expanded from 32 to 73 names.
#   The 50/50 pool (100 scored names) is introduced with pool "2026Q3".
#
# Fields:
#   ticker: exchange ticker (use primary listing)
#   name: display name (English + Chinese where applicable)
#   leg: US | China | Pre-IPO
#   layer: L1 (Energy) | L2 (Chips) | L3 (Infra) | L4 (Models) | L5 (Apps)
#   pure_play_pct: estimated % of revenue tied to AI workloads (0-100)
#   primary_exchange: exchange code for fetcher routing
#   policy_premium: true if state-directed valuation premium applies
#   cohort: core (45/leg) | newcomer (5/leg) | watch (not scored this quarter)
#   pool: active quarter id (e.g. "2026Q3") or null (watchlist / observation)
#   listed_at: first public listing date (rotation's "new listing" signal)
#   notes: free-text context
"""


def _base_entry(ticker: str, data: tuple) -> dict:
    name, leg, layer, pure_play, exchange, listed_at, notes = data
    return {
        "ticker": ticker,
        "name": name,
        "leg": leg,
        "layer": layer,
        "pure_play_pct": pure_play,
        "primary_exchange": exchange,
        "policy_premium": False,
        "cohort": "watch",
        "pool": None,
        "listed_at": listed_at,
        "notes": notes,
    }


# Every ticker that should be in the pool (legacy + new) — used for idempotent
# re-runs, where already-appended entries appear in the input file.
# Note: EUROPE_TO_US entries can appear under either the legacy ticker
# (SMEGY/ABB) or the yfinance-valid replacement (SMEGF/ABBNY) on re-runs.
_EUROPE_TICKERS = set(EUROPE_TO_US) | {v[0] for v in EUROPE_TO_US.values()}
POOL_CORE_TICKERS = (
    US_CORE_LEGACY | CHINA_CORE_LEGACY
    | set(US_ADD_CORE) | set(CHINA_ADD_CORE) | _EUROPE_TICKERS
)
POOL_NEWCOMER_TICKERS = (
    CHINA_NEWCOMER_LEGACY | set(US_NEWCOMER) | set(CHINA_NEWCOMER)
)
POOL_TICKERS = POOL_CORE_TICKERS | POOL_NEWCOMER_TICKERS


def _role_for(ticker: str) -> str:
    if ticker in POOL_NEWCOMER_TICKERS:
        return "newcomer"
    return "core"


def build_universe(pool_id: str, path: Path = Path("config/universe.yaml")) -> list[dict]:
    raw = yaml.safe_load(path.open())
    entries: list[dict] = []
    seen: set[str] = set()

    for item in raw:
        ticker = str(item["ticker"])
        seen.add(ticker)
        e = dict(item)
        e["listed_at"] = e.get("listed_at")

        if ticker in POOL_TICKERS:
            e["cohort"] = _role_for(ticker)
            e["pool"] = pool_id
        else:
            e["cohort"] = "watch"
            e["pool"] = None

        if ticker in CHINA_NEWCOMER_LEGACY and e["listed_at"] is None:
            # Zhipu / MiniMax listed in HK in 2026 (approx. per registry).
            e["listed_at"] = "2026-01-01"
        if ticker in EUROPE_TO_US:
            new_ticker, note_suffix = EUROPE_TO_US[ticker]
            e["ticker"] = new_ticker
            e["name"] = note_suffix
            e["leg"] = "US"
            e["cohort"] = "core"
            e["pool"] = pool_id
            # Append once — the script is meant to be re-runnable against its
            # own output, and an unconditional append grows the note on every
            # pass until the entry is a wall of repeated suffixes.
            marker = "（原 Europe-ref，已并入 US 池）"
            notes = e.get("notes", "") or ""
            e["notes"] = notes if marker in notes else f"{notes}{marker}"
        # Pre-IPO legacy entries stay leg=Pre-IPO, cohort=watch, pool=null.
        entries.append(e)

    # Append new entries (skip any that already exist — idempotent).
    new_sets = {
        **{t: ("core", d) for t, d in US_ADD_CORE.items()},
        **{t: ("core", d) for t, d in CHINA_ADD_CORE.items()},
        **{t: ("newcomer", d) for t, d in US_NEWCOMER.items()},
        **{t: ("newcomer", d) for t, d in CHINA_NEWCOMER.items()},
        **{t: ("watch", d) for t, d in US_WATCH.items()},
        **{t: ("watch", d) for t, d in CHINA_WATCH.items()},
        **{t: ("watch", d) for t, d in PREIPO_OBSERVE.items()},
    }
    for ticker, (cohort, data) in new_sets.items():
        if ticker in seen:
            continue
        e = _base_entry(ticker, data)
        e["cohort"] = cohort
        if cohort != "watch":
            e["pool"] = pool_id
        entries.append(e)

    return entries


def main() -> None:
    parser = argparse.ArgumentParser(description="Build the quarterly 50/50 pool universe")
    parser.add_argument("--pool", default=POOL_ID, help="Quarter id, e.g. 2026Q3")
    parser.add_argument("--universe", type=Path, default=Path("config/universe.yaml"))
    args = parser.parse_args()

    entries = build_universe(args.pool, args.universe)
    payload = HEADER + "\n" + yaml.safe_dump(
        entries, sort_keys=False, allow_unicode=True, default_flow_style=False
    )
    args.universe.write_text(payload, encoding="utf-8")

    from collections import Counter

    counts = Counter((e["leg"], e.get("cohort"), e.get("pool")) for e in entries)
    print(f"Wrote {len(entries)} entries to {args.universe} (pool={args.pool})")
    for key in sorted(counts):
        print(f"  {key[0]:10} cohort={str(key[1]):9} pool={str(key[2]):7} n={counts[key]}")


if __name__ == "__main__":
    main()
