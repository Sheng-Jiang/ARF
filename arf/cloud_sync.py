"""Cloud data sync for ARF.

Two authoritative sources feed the local DuckDB:

* **Google Cloud Storage** (``gs://<bucket>/arf.db``) — the global database.
  The batch pipeline downloads it, appends a run, and uploads it again.
* **Tencent Cloud Lighthouse** — the domestic China leg. Lighthouse runs
  ``arf.run --leg China`` on a systemd timer and uploads its result to the
  same GCS object, so from Cloud Run there is nothing to SSH into; refreshing
  GCS already contains the China leg.

The webapp's GCS mode simply drops its cached connection and re-downloads the
object. Local mode downloads and merges it here, and optionally rsyncs the
Lighthouse DB when SSH is configured.

Merges are schema-safe: only columns present in *both* databases are copied
(``INSERT ... BY NAME`` semantics), so a remote DB written by an older build
cannot abort the sync with a column-count error.
"""

from __future__ import annotations

import contextlib
import os
import shutil
import subprocess
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

import duckdb

DEFAULT_BUCKET = os.getenv("GCS_BUCKET", "arf-data-ai-rf")
DEFAULT_DB_OBJECT = os.getenv("GCS_DB_OBJECT", "arf.db")
DEFAULT_LIGHTHOUSE_HOST = os.getenv("ARF_LIGHTHOUSE_HOST", "lighthouse")
REMOTE_LIGHTHOUSE_DB = os.getenv("ARF_LIGHTHOUSE_DB", "/home/ubuntu/ARF/data/arf.db")


class SyncError(RuntimeError):
    """A sync step failed; the caller must surface it, never report success."""


@dataclass
class SyncResult:
    source: str
    status: Literal["ok", "skipped", "error"]
    message: str
    rows: dict[str, int] = field(default_factory=dict)

    @property
    def ok(self) -> bool:
        return self.status == "ok"


# ---------------------------------------------------------------------------
# DuckDB merge
# ---------------------------------------------------------------------------


def _base_tables(conn: duckdb.DuckDBPyConnection, database: str) -> set[str]:
    rows = conn.execute(
        """
        SELECT table_name FROM duckdb_tables()
        WHERE database_name = ? AND schema_name = 'main'
        """,
        [database],
    ).fetchall()
    return {row[0] for row in rows}


def _columns(conn: duckdb.DuckDBPyConnection, qualified: str) -> list[str]:
    rows = conn.execute(f"PRAGMA table_info('{qualified}')").fetchall()
    # PRAGMA table_info returns (cid, name, type, notnull, dflt_value, pk)
    return [row[1] for row in rows]


def merge_duckdb(
    source_db: str | Path,
    target_db: str | Path,
    *,
    connection: duckdb.DuckDBPyConnection | None = None,
) -> dict[str, int]:
    """Merge every table shared by *source_db* and *target_db*.

    Existing rows win (``INSERT OR IGNORE``), so a merge is idempotent and a
    re-run cannot duplicate snapshots or prices. Raises SyncError on failure.
    """
    source_path = Path(source_db)
    target_path = Path(target_db)
    if not source_path.exists():
        raise SyncError(f"source database not found: {source_path}")

    owns_connection = connection is None
    if owns_connection:
        if not target_path.exists():
            target_path.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source_path, target_path)
            return {"*": -1}
        connection = duckdb.connect(str(target_path))

    assert connection is not None
    attached = False
    try:
        connection.execute(f"ATTACH '{source_path.as_posix()}' AS src (READ_ONLY)")
        attached = True
        main_database = connection.execute("SELECT current_database()").fetchone()[0]
        source_tables = _base_tables(connection, "src")
        target_tables = _base_tables(connection, main_database)
        merged: dict[str, int] = {}

        for table in sorted(source_tables & target_tables):
            source_cols = _columns(connection, f"src.{table}")
            target_cols = _columns(connection, f"main.{table}")
            shared = [col for col in target_cols if col in set(source_cols)]
            if not shared:
                continue
            quoted = ", ".join(f'"{col}"' for col in shared)
            before = connection.execute(f'SELECT COUNT(*) FROM main."{table}"').fetchone()[0]
            connection.execute(
                f'INSERT OR IGNORE INTO main."{table}" ({quoted}) '
                f'SELECT {quoted} FROM src."{table}"'
            )
            after = connection.execute(f'SELECT COUNT(*) FROM main."{table}"').fetchone()[0]
            merged[table] = int(after - before)

        return merged
    except Exception as exc:  # noqa: BLE001 — converted to a typed sync failure
        raise SyncError(f"merge failed: {exc}") from exc
    finally:
        if attached:
            with contextlib.suppress(Exception):
                connection.execute("DETACH src")
        if owns_connection:
            connection.close()


# ---------------------------------------------------------------------------
# Google Cloud Storage
# ---------------------------------------------------------------------------


def _storage_client():
    from google.cloud import storage  # type: ignore[import]

    return storage.Client()


def gcs_blob_info(
    bucket: str = DEFAULT_BUCKET, object_name: str = DEFAULT_DB_OBJECT
) -> dict[str, object]:
    """Metadata of the authoritative DB object, for the cockpit's status line."""
    try:
        blob = _storage_client().bucket(bucket).get_blob(object_name)
        if blob is None:
            return {}
        return {
            "bucket": bucket,
            "object": object_name,
            "size": blob.size,
            "updated": blob.updated,
            "generation": blob.generation,
        }
    except Exception:  # noqa: BLE001 — status metadata is best-effort
        return {}


def download_gcs_db(
    destination: str | Path,
    bucket: str = DEFAULT_BUCKET,
    object_name: str = DEFAULT_DB_OBJECT,
) -> Path:
    """Download the authoritative DuckDB object to *destination*."""
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    try:
        blob = _storage_client().bucket(bucket).blob(object_name)
        blob.download_to_filename(str(destination))
    except Exception as exc:  # noqa: BLE001 — fall back to the gcloud CLI locally
        if shutil.which("gcloud"):
            command = [
                "gcloud", "storage", "cp",
                f"gs://{bucket}/{object_name}", str(destination),
                "--quiet",
            ]
            result = subprocess.run(command, capture_output=True, text=True, timeout=120)
            if result.returncode != 0:
                raise SyncError(f"GCS download failed: {result.stderr.strip()}") from exc
        else:
            raise SyncError(f"GCS download failed: {exc}") from exc

    if not destination.exists() or destination.stat().st_size == 0:
        raise SyncError(f"GCS download produced no data: gs://{bucket}/{object_name}")
    return destination


def sync_from_gcs(
    target_db: str | Path,
    *,
    connection: duckdb.DuckDBPyConnection | None = None,
    bucket: str = DEFAULT_BUCKET,
    object_name: str = DEFAULT_DB_OBJECT,
) -> SyncResult:
    target = Path(target_db)
    with tempfile.TemporaryDirectory(prefix="arf-gcs-") as tmp:
        downloaded = Path(tmp) / "arf.db"
        try:
            download_gcs_db(downloaded, bucket=bucket, object_name=object_name)
            rows = merge_duckdb(downloaded, target, connection=connection)
        except SyncError as exc:
            return SyncResult("gcs", "error", str(exc))
    return SyncResult("gcs", "ok", f"merged gs://{bucket}/{object_name}", rows)


# ---------------------------------------------------------------------------
# Tencent Cloud Lighthouse
# ---------------------------------------------------------------------------


def sync_from_lighthouse(
    target_db: str | Path,
    *,
    connection: duckdb.DuckDBPyConnection | None = None,
    host: str = DEFAULT_LIGHTHOUSE_HOST,
    remote_db: str = REMOTE_LIGHTHOUSE_DB,
) -> SyncResult:
    if os.getenv("DATA_SOURCE", "local").lower() == "gcs":
        return SyncResult(
            "lighthouse",
            "skipped",
            "Cloud Run has no SSH path; Lighthouse publishes its China leg to GCS on its timer.",
        )

    check = subprocess.run(
        ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=5", host, "true"],
        capture_output=True,
        text=True,
        timeout=15,
    )
    if check.returncode != 0:
        return SyncResult("lighthouse", "error", f"SSH unreachable: {check.stderr.strip()}")

    with tempfile.TemporaryDirectory(prefix="arf-lh-") as tmp:
        downloaded = Path(tmp) / "arf.db"
        result = subprocess.run(
            ["rsync", "-az", f"{host}:{remote_db}", str(downloaded)],
            capture_output=True,
            text=True,
            timeout=120,
        )
        if result.returncode != 0 or not downloaded.exists():
            return SyncResult("lighthouse", "error", f"rsync failed: {result.stderr.strip()}")
        try:
            rows = merge_duckdb(downloaded, Path(target_db), connection=connection)
        except SyncError as exc:
            return SyncResult("lighthouse", "error", str(exc))
    return SyncResult("lighthouse", "ok", f"merged {host}:{remote_db}", rows)


def sync_dual_cloud(
    target_db: str | Path,
    *,
    connection: duckdb.DuckDBPyConnection | None = None,
) -> dict[str, SyncResult]:
    """Sync both sources, reporting each independently."""
    return {
        "gcs": sync_from_gcs(target_db, connection=connection),
        "lighthouse": sync_from_lighthouse(target_db, connection=connection),
    }
