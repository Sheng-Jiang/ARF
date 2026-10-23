"""Dual-cloud sync CLI.

Thin wrapper around :mod:`arf.cloud_sync`, which the CIO cockpit also uses.
Both sources publish into the same GCS DuckDB object; this command merges the
GCS copy and (locally, when SSH is configured) the Lighthouse copy into a
local database.

Usage:
    python scripts/sync_cloud_data.py --source all
    python scripts/sync_cloud_data.py --source lighthouse
    python scripts/sync_cloud_data.py --source gcs
"""

from __future__ import annotations

import argparse
import logging
import os
import sys
from pathlib import Path

from arf.cloud_sync import (
    SyncResult,
    sync_dual_cloud,
    sync_from_gcs,
    sync_from_lighthouse,
)
from arf.db import init_db

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger("arf.sync")

DEFAULT_LOCAL_DB = Path(os.getenv("LOCAL_DB_PATH", "data/arf.db"))


def main() -> int:
    parser = argparse.ArgumentParser(description="Synchronize ARF data from Lighthouses and GCS.")
    parser.add_argument(
        "--source", choices=["all", "lighthouse", "gcs"], default="all"
    )
    parser.add_argument(
        "--target", default=str(DEFAULT_LOCAL_DB), help="local DuckDB to merge into"
    )
    args = parser.parse_args()

    target = Path(args.target)
    target.parent.mkdir(parents=True, exist_ok=True)
    # Migrate before merging so new tables/columns exist locally.
    init_db(target).close()

    if args.source == "all":
        results = sync_dual_cloud(target)
    elif args.source == "gcs":
        results = {"gcs": sync_from_gcs(target)}
    else:
        results = {"lighthouse": sync_from_lighthouse(target)}

    exit_code = 0
    for name, result in results.items():
        _report(name, result)
        if result.status == "error":
            exit_code = 1
    return exit_code


def _report(name: str, result: SyncResult) -> None:
    if result.status == "ok":
        log.info("✅ %s: %s %s", name, result.message, result.rows)
    elif result.status == "skipped":
        log.info("ℹ️  %s: %s", name, result.message)
    else:
        log.error("❌ %s: %s", name, result.message)


if __name__ == "__main__":
    sys.exit(main())
