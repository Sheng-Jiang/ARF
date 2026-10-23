# ADR-0001: Hybrid-Repo Single-Container Architecture for AI CIO Integration

* **Status:** Accepted
* **Date:** 2026-10-24
* **Deciders:** Sheng Jiang (Lead), Antigravity AI
* **Context:** ARF (AI Relevance Factor) & `ai-hedge-fund` Integration on Google Cloud Run

---

## 1. Context and Problem Statement

The ARF system calculates narrative exposure, valuation stretch, and bubble thermometry across 73 companies in Jensen Huang's 5-layer AI stack. To complete the investment workflow, we introduced the **"AI CIO (投资总监)" Cockpit** (`webapp/pages/10_💼_CIO_投资总监.py`), which replays the ARF investment mandate over historical market windows and produces real-time order books, portfolio holdings, factor exposures, and performance scorecards.

However, the core hedge fund simulation engine, multi-agent evaluation framework, and mandate execution logic reside in a separate open-source repository: [`Sheng-Jiang/ai-hedge-fund`](https://github.com/Sheng-Jiang/ai-hedge-fund) (package `aihf`, root module `hedge_fund`).

### Challenges:
1. **Independent Evolution:** `ai-hedge-fund` is a standalone quantitative/agentic simulation framework with its own contributors, dependencies, and git history. Merging it directly into ARF would cause monorepo bloat and make upstream synchronization painful.
2. **Production Deployment Simplicity:** The production deployment runs on Google Cloud Run (`arf-webapp`) in `asia-east1`. Orchestrating multiple microservices (one for Streamlit UI, one for the simulation engine) introduces latency, inter-service networking overhead, and multi-service cold-start penalties.
3. **DuckDB Concurrency Constraints:** DuckDB prevents a second connection with conflicting configurations from opening against the same file on disk in a single process.
4. **Reproducibility & Stability:** Production cloud builds must be strictly deterministic and not break when `ai-hedge-fund` receives experimental commits on `main`.

---

## 2. Considered Options

* **Option 1: Monorepo Merge (Physical Git Merge)**
  * *Description:* Merge `ai-hedge-fund` source code directly into `ARF/hedge_fund`.
  * *Pros:* Single repository, simple imports.
  * *Cons:* Destroys separation of concerns, complicates git blame/history, makes upstream sync with `virattt/ai-hedge-fund` extremely labor-intensive.

* **Option 2: Microservices Architecture (Two Cloud Run Services + REST/gRPC)**
  * *Description:* Deploy `ai-hedge-fund` as an independent API service and have `arf-webapp` invoke backtest endpoints.
  * *Pros:* Complete process and language isolation.
  * *Cons:* Severe latency serialization penalty when passing multi-year daily price matrices; dual container bills; network failure modes during interactive Streamlit slider changes.

* **Option 3: Git Submodule**
  * *Description:* Include `ai-hedge-fund` as a git submodule inside `ARF/external/ai-hedge-fund`.
  * *Pros:* Pinned to a specific commit.
  * *Cons:* Clunky developer workflow (`git submodule update --init`), fragile Docker caching in Google Cloud Build, requires manual `sys.path` tampering.

* **Option 4: Single Docker Container via Git-Pinned Package Dependency with In-Memory Adapter (Selected)**
  * *Description:* Install `ai-hedge-fund` as a first-class Python package (`aihf`) directly from a pinned Git release tag during the Docker image build. Use an in-memory data adapter (`PreloadedDataClient`) to feed DuckDB prices directly into the backtest engine without disk contention.

---

## 3. Decision

We chose **Option 4: Single Docker Container via Git-Pinned Package Dependency with In-Memory Adapter**.

### Architectural Blueprint

```
+-------------------------------------------------------------------------+
|                  Google Cloud Run Service: arf-webapp                   |
|                                                                         |
|  +-------------------------------------------------------------------+  |
|  |                     Streamlit UI & Routing                        |  |
|  |         (webapp/app.py, webapp/pages/10_💼_CIO_投资总监.py)        |  |
|  +---------------------------------+---------------------------------+  |
|                                    |                                    |
|                                    v                                    |
|  +---------------------------------+---------------------------------+  |
|  |                     ARF CIO Bridge (arf/cio.py)                   |  |
|  |       - default_mandate_path: config/arf-mandate.yaml             |  |
|  |       - PreloadedDataClient: in-memory price slices               |  |
|  +---------------------------------+---------------------------------+  |
|                                    |                                    |
|                                    v                                    |
|  +---------------------------------+---------------------------------+  |
|  |              aihf Package (Installed from Sheng-Jiang/ai-hedge-fund) |  |
|  |       - hedge_fund.fund: load_spec & Fund engine                  |  |
|  |       - hedge_fund.backtesting: backtest_fund                     |  |
|  |       - hedge_fund.scorecard: scorecard                           |  |
|  +---------------------------------+---------------------------------+  |
|                                    ^                                    |
|                                    | In-memory                          |
|  +---------------------------------+---------------------------------+  |
|  |                     DuckDB Data Layer (data/arf.db)               |  |
|  |       - Downloaded / Synced from GCS: gs://arf-data-ai-rf         |  |
|  +-------------------------------------------------------------------+  |
+-------------------------------------------------------------------------+
```

---

## 4. Key Implementation Details

### A. Git-Pinned Package Dependency (`pyproject.toml`)
In ARF's `pyproject.toml`, `aihf` is declared under the `[project.optional-dependencies].webapp` extra:
```toml
[project.optional-dependencies]
webapp = [
    "streamlit>=1.36",
    "google-cloud-storage>=2.16",
    "google-cloud-run>=0.10",
    "google-genai>=0.3",
    "pyecharts>=2.0.8",
    "streamlit-echarts>=0.4.0",
    "socksio>=1.0",
    # Pinned to an immutable release tag in our fork to prevent drift
    "aihf @ git+https://github.com/Sheng-Jiang/ai-hedge-fund.git@arf-prod-2026-10-23",
]
```

### B. Docker Build Pipeline (`Dockerfile` & `cloudbuild.yaml`)
1. In `Dockerfile`, `git` and `gcc` are installed to allow `pip` to clone and build `aihf` using its `poetry-core` build backend:
   ```dockerfile
   RUN apt-get update && apt-get install -y --no-install-recommends gcc git && \
       rm -rf /var/lib/apt/lists/*
   RUN pip install --no-cache-dir -e ".[webapp]"
   ```
2. Google Cloud Build (`cloudbuild.yaml`) builds this single image, pushes it to Google Artifact Registry (`asia-east1-docker.pkg.dev/ai-rf-497701/arf/arf-webapp`), and deploys it to Cloud Run.

### C. In-Memory Data Client & Zero-Contention Bridge (`arf/cio.py`)
Streamlit maintains an open connection to `data/arf.db`. To prevent DuckDB file locks:
1. `arf.cio.PreloadedDataClient` queries historical price frames from ARF's DuckDB connection once.
2. It slices the rolling window in memory and implements `DataClient` (`get_price_history`, `get_prices`), feeding the backtest engine zero-latency ticks without reading disk or contacting external APIs.

### D. ABI & Binary Compatibility Harmonization
* `ai-hedge-fund` pins `numpy < 2.0`.
* Default PyPI builds of `pyarrow >= 19` require NumPy 2.x and fail upon import on Linux containers.
* **Resolution:** ARF's `pyproject.toml` pins `"pyarrow>=14.0,<19"` so all compiled extensions cleanly share the NumPy 1.x ABI.

### E. Cloud Run Compute & Memory Sizing
Because `10_💼_CIO_投资总监.py` executes in-memory vector backtests across 36 US leg universe tickers upon slider selection:
* Cloud Run memory was upgraded from 512Mi to **1Gi** (`--memory=1Gi --cpu=1`) in `cloudbuild.yaml`.
* Timeout is configured to 900s to allow intensive scenario replays.

---

## 5. Consequences & Trade-offs

### Positive Consequences
* **Unified Single Artifact:** Exactly one container image is built, versioned, and deployed to Cloud Run.
* **Zero Microservice Overhead:** No inter-service latency, no network hops, and zero complex API authentication between UI and execution engine.
* **Clean Repo Boundaries:** `ai-hedge-fund` remains an independent codebase; bug fixes or enhancements can be developed, tested, and tagged independently.
* **Deterministic Deployments:** Tag-based pinning (`@arf-prod-2026-10-23`) ensures production builds never break due to upstream branch updates.

### Trade-offs & Mitigations
* **Build-Time Network Access:** Cloud Build requires outbound internet access to clone `github.com/Sheng-Jiang/ai-hedge-fund.git`. Mitigated by Cloud Build's fast global network.
* **Release Flow:** Deploying a change made inside `ai-hedge-fund` requires creating a new git tag in that repo and updating the tag in ARF's `pyproject.toml`.
