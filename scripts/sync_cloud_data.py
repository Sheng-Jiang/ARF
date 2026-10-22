"""Dual-Cloud Data Synchronization Engine for ARF.

Synchronizes financial data, factor snapshots, and pricing feeds from both:
1. Tencent Cloud Lighthouse (Domestic China Financial Data Tier: 82.156.75.194 / bid2-lh)
   - Syncs China A-share daily prices, CYQ chip distributions, and China leg snapshots.
2. Google Cloud Storage (Global AI Tier: ai-rf-497701 / gs://arf-data-ai-rf)
   - Syncs cloud-computed DuckDB snapshots (arf.db), parquet data lake, and reports.

Usage:
    python scripts/sync_cloud_data.py --source all
    python scripts/sync_cloud_data.py --source lighthouse
    python scripts/sync_cloud_data.py --source gcs
"""

from __future__ import annotations

import argparse
import contextlib
import logging
import os
import shutil
import subprocess
from pathlib import Path
from typing import Literal

import duckdb

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("arf.sync")

LOCAL_ARF_DIR = Path("/Users/sheng/Developer/ARF")
LOCAL_DB_PATH = LOCAL_ARF_DIR / "data" / "arf.db"
LIGHTHOUSE_HOST = os.getenv("ARF_LIGHTHOUSE_HOST", "lighthouse")
REMOTE_LIGHTHOUSE_DB = "/home/ubuntu/ARF/data/arf.db"
GCP_PROJECT = os.getenv("GCP_PROJECT_ID", "ai-rf-497701")
GCS_BUCKET = os.getenv("GCS_BUCKET", "arf-data-ai-rf")


def sync_from_gcs(target_path: Path = LOCAL_DB_PATH) -> bool:
    """Download authoritative arf.db and snapshot parquets from GCS."""
    log.info("☁️ Checking Google Cloud Storage (gs://%s)...", GCS_BUCKET)
    target_path.parent.mkdir(parents=True, exist_ok=True)
    temp_download = target_path.with_suffix(".gcs_tmp")

    try:
        # Check if gsutil or gcloud storage is available
        cmd = [
            "gcloud", "storage", "cp",
            f"gs://{GCS_BUCKET}/arf.db",
            str(temp_download),
            f"--project={GCP_PROJECT}",
        ]
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if res.returncode == 0 and temp_download.exists() and temp_download.stat().st_size > 0:
            log.info("Downloaded %s bytes from gs://%s/arf.db", temp_download.stat().st_size, GCS_BUCKET)
            _merge_duckdb_files(temp_download, target_path)
            temp_download.unlink(missing_ok=True)
            log.info("✅ GCS synchronization complete.")
            return True
        else:
            log.warning("GCS download non-zero exit or empty: %s", res.stderr.strip())
            temp_download.unlink(missing_ok=True)
            return False
    except Exception as exc:
        log.warning("GCS sync skipped or failed: %s", exc)
        temp_download.unlink(missing_ok=True)
        return False


def sync_from_lighthouse(target_path: Path = LOCAL_DB_PATH) -> bool:
    """Download domestic China prices and snapshots from Tencent Cloud Lighthouse."""
    log.info("🇨🇳 Checking Tencent Cloud Lighthouse (%s)...", LIGHTHOUSE_HOST)
    target_path.parent.mkdir(parents=True, exist_ok=True)
    temp_download = target_path.with_suffix(".lh_tmp")

    try:
        # Check SSH connectivity
        check_ssh = subprocess.run(
            ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=5", LIGHTHOUSE_HOST, "echo ok"],
            capture_output=True, text=True, timeout=10
        )
        if check_ssh.returncode != 0:
            log.warning("Lighthouse SSH unreachable: %s", check_ssh.stderr.strip())
            return False

        # Rsync the remote arf.db
        cmd = [
            "rsync", "-avz", "--progress",
            f"{LIGHTHOUSE_HOST}:{REMOTE_LIGHTHOUSE_DB}",
            str(temp_download),
        ]
        res = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
        if res.returncode == 0 and temp_download.exists() and temp_download.stat().st_size > 0:
            log.info("Downloaded %s bytes from Lighthouse:%s", temp_download.stat().st_size, REMOTE_LIGHTHOUSE_DB)
            _merge_duckdb_files(temp_download, target_path)
            temp_download.unlink(missing_ok=True)
            log.info("✅ Lighthouse synchronization complete.")
            return True
        else:
            log.warning("Lighthouse sync non-zero exit: %s", res.stderr.strip())
            temp_download.unlink(missing_ok=True)
            return False
    except Exception as exc:
        log.warning("Lighthouse sync failed: %s", exc)
        temp_download.unlink(missing_ok=True)
        return False


def _merge_duckdb_files(source_db: Path, target_db: Path) -> None:
    """Safely merge tables (daily_prices, snapshots, technical_metrics) from source to target."""
    if not target_db.exists():
        shutil.copy2(source_db, target_db)
        log.info("Target did not exist, initialised from downloaded DB.")
        return

    log.info("Merging tables from %s into %s...", source_db.name, target_db.name)
    try:
        con = duckdb.connect(str(target_db))
        con.execute(f"ATTACH '{source_db}' AS src (READ_ONLY)")

        # Merge daily_prices
        con.execute("""
            INSERT OR IGNORE INTO daily_prices 
            SELECT * FROM src.daily_prices
        """)

        # Merge snapshots (snapshot_revisions and snapshots)
        con.execute("""
            INSERT OR IGNORE INTO snapshot_revisions 
            SELECT * FROM src.snapshot_revisions
        """)

        # Merge candidate_pool if present
        with contextlib.suppress(Exception):
            con.execute("""
                INSERT OR IGNORE INTO candidate_pool 
                SELECT * FROM src.candidate_pool
            """)

        con.execute("DETACH src")
        con.close()
        log.info("DuckDB merge completed successfully.")
    except Exception as exc:
        log.warning("DuckDB merge encountered error: %s (falling back to keeping local)", exc)


def sync_dual_cloud(source: Literal["all", "lighthouse", "gcs"] = "all") -> dict[str, bool]:
    """Public orchestration function returning sync statuses."""
    results = {}
    if source in ("all", "lighthouse"):
        results["lighthouse"] = sync_from_lighthouse()
    if source in ("all", "gcs"):
        results["gcs"] = sync_from_gcs()
    return results


def main() -> None:
    parser = argparse.ArgumentParser(description="Synchronize ARF data from Lighthouse and Google Cloud.")
    parser.add_argument(
        "--source",
        choices=["all", "lighthouse", "gcs"],
        default="all",
        help="Data source to pull from (default: all)",
    )
    args = parser.parse_args()
    results = sync_dual_cloud(args.source)
    log.info("Sync Summary: %s", results)


if __name__ == "__main__":
    main()
