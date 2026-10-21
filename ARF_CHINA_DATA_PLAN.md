# ARF China Data Ingestion Plan: Tencent Cloud Lighthouse Architecture

## 1. Problem Statement & Scope

The ARF (AI Relevance Factor) universe monitors 73 companies, including **37 companies in the China leg** (Shenzhen, Shanghai, and Hong Kong-listed AI leaders). 

To compute ARF scores, technical indicators, and CYQ chip distributions, the pipeline relies on domestic mainland financial APIs and scrapers:
- **AkShare / Eastmoney (东方财富)**: Historical and daily prices, research reports, consensus EPS.
- **Tencent Finance (腾讯行情)**: Real-time and daily price history (`stock_zh_a_hist_tx`).
- **Baostock**: Fundamental quarterly reports and historical P/S multiples.

### The Overseas IP Bottleneck
When running from Google Cloud Run (`asia-east1`, Taiwan) or overseas developer machines, these mainland financial servers frequently:
1. **Return HTTP 403 Forbidden** due to geo-blocking non-mainland IP addresses.
2. **Trigger anti-scraping CAPTCHAs** or aggressive rate-limiting.
3. **Drop connections** resulting in empty snapshot rows and unranked tickers in weekly reports.

> **Note on Web App Access**: User telemetry confirms that the ARF Streamlit web app deployed on Google Cloud Run (`asia-east1`) is accessible to mainland China users without significant network issues. Therefore, the Tencent Cloud Lighthouse server (`82.156.75.194`) is dedicated **100% to data ingestion and pipeline acceleration**.

---

## 2. Dual-Engine Architecture

ARF employs a specialized hybrid topology:

```
┌─────────────────────────────────────────────────────────────┐
│             GLOBAL / AI TIER (Google Cloud)                 │
│                                                             │
│   • GCP Project: ai-rf-497701 (Region: asia-east1)          │
│   • Google Gemini 3.8 Flash (LLM Research & IDR synthesis)  │
│   • US Market Ingestion (yfinance, SEC EDGAR XBRL)          │
│   • Streamlit Web App (arf-webapp)                          │
│   • Authoritative Data Lake (GCS: gs://arf-data-ai-rf)      │
└──────────────┬──────────────────────────────▲───────────────┘
               │                              │
         ARF_CHINA_PROXY             Incremental DuckDB Sync
         (SOCKS5 / HTTP)                 (GCS Upload)
               │                              │
┌──────────────▼──────────────────────────────┴───────────────┐
│        DOMESTIC CHINA DATA TIER (Tencent Cloud)             │
│                                                             │
│   • Host: Ubuntu-kKLi (82.156.75.194 / "lighthouse")        │
│   • Specs: 4 vCPU, 4GB RAM, 40GB SSD (Ubuntu 22.04 LTS)     │
│   • Native domestic network: Eastmoney, Tencent, Baostock   │
│                                                             │
│   [Path A: Forward Proxy]      [Path B: Domestic Runner]    │
│   Scoped SOCKS5/HTTP tunnel     Scheduled post-close cron   │
│   for Cloud Run & local dev     (16:30 CST) syncing to GCS  │
└─────────────────────────────────────────────────────────────┘
```

---

## 3. Path A: Scoped Domestic Forward Proxy

Rather than routing all outbound container traffic through a proxy (which would break Google Gemini API calls due to mainland GFW restrictions), ARF implements **targeted proxy scoping**:

1. **Selective Context Manager** ([`arf/fetchers/proxy.py`](file:///Users/sheng/Developer/ARF/arf/fetchers/proxy.py)):
   - Evaluates `ARF_CHINA_PROXY` or `CHINA_DATA_PROXY`, or auto-detects a local SSH tunnel on `127.0.0.1:10808`. A general-purpose `ALL_PROXY` (usually an overseas VPN) is ignored on purpose.
   - Wraps only China-specific scraper calls ([`arf/fetchers/akshare.py`](file:///Users/sheng/Developer/ARF/arf/fetchers/akshare.py), [`arf/fetchers/research.py`](file:///Users/sheng/Developer/ARF/arf/fetchers/research.py)) via `with use_china_proxy():`.
   - Routing is **thread-scoped**: the context flags the calling thread and a `requests.Session.request` hook applies the proxy there, rather than mutating process-wide `HTTP_PROXY` variables. Concurrent US/yfinance fetches in the same worker pool, and Gemini API calls, are untouched. This covers AkShare because it uses `requests`.
   - Baostock opens a raw TCP session, so environment proxies and this hook cannot route it — run Baostock jobs on the Lighthouse runner (Path B).
   - SOCKS5 endpoints require `pysocks` (declared in `pyproject.toml`).

2. **Developer Workstation Integration** ([`scripts/tunnel_china.sh`](file:///Users/sheng/Developer/ARF/scripts/tunnel_china.sh)):
   - Zero-configuration SSH dynamic SOCKS5 tunnel over port 22:
     ```bash
     scripts/tunnel_china.sh start     # Opens encrypted tunnel on 127.0.0.1:10808
     scripts/tunnel_china.sh status    # Verifies egress IP is 82.156.75.194
     scripts/tunnel_china.sh stop      # Shuts down background tunnel
     eval "$(scripts/tunnel_china.sh env)"  # Export ARF_CHINA_PROXY in this shell
     ```
   - Automatically detected by `get_china_proxy()` when active.

3. **Cloud Run / Production Batch Integration**:
   - Authenticated proxy container (`gost` / `tinyproxy`) running on Lighthouse.
   - Proxy URL stored securely in GCP Secret Manager: `projects/ai-rf-497701/secrets/china-data-proxy`.
   - Injected into Cloud Run Job `arf-pipeline` as `ARF_CHINA_PROXY`.

---

## 4. Path B: Domestic Scheduled Batch Runner

For high-volume historical crawls and vectorised CYQ chip distribution calculations, running directly on the domestic server eliminates network latency entirely:

1. **Job Scope**:
   - Executes daily at **16:30 CST** (30 minutes after A-share market close).
   - Syncs all 37 China tickers: daily bars, turnover, chip profit ratios, and research reports.
   - Computes local technical indicators and writes to `data/arf.db`.

2. **GCS Storage Bridge**:
   - Authenticates using GCP service account credentials (`arf-pipeline-runner@ai-rf-497701.iam.gserviceaccount.com`).
   - Uploads snapshot parquet files to `gs://arf-data-ai-rf/data/snapshots/`.
   - Uploads incremental `arf.db` to `gs://arf-data-ai-rf/arf.db`.
   - The web app running on Cloud Run reads directly from GCS, instantly reflecting the fresh domestic data.

---

## 5. Development & Deployment Milestones

| Milestone | Deliverables | Target Status |
| :--- | :--- | :--- |
| **M1: Scoped Proxy Engine** | `arf/fetchers/proxy.py`, `scripts/tunnel_china.sh`, integration in `akshare.py` and `research.py`. Unit tests passing. | **Done & Verified** |
| **M2: Lighthouse Batch Sync Script** | `scripts/sync_china_lighthouse.sh` to execute China leg ingestion on Lighthouse and push snapshots to GCS. | Next |
| **M3: Production Secret & Cloud Run Link** | Configure Secret Manager `china-data-proxy` in `ai-rf-497701`; pass to `arf-pipeline` Cloud Run job. | Next |
| **M4: Automated Systemd Cron** | Install `arf-china-sync.timer` on Lighthouse for automated 16:30 CST daily runs. | Next |
