"""GCS storage helpers for pipeline I/O.

The pipeline writes locally first, then optionally syncs artifacts back to GCS
so the webapp (which reads from `gs://<bucket>/arf.db`) sees the new snapshot.

Configuration via env vars:
    OUTPUT_TARGET   "local" (default) or "gcs"
    GCS_BUCKET      bucket name (required when OUTPUT_TARGET=gcs)
    GCS_DB_OBJECT   object key for the DuckDB file (default "arf.db")
    GCS_PREFIX      prefix for snapshot parquet and reports (default "")
"""
import logging
import os
from pathlib import Path

log = logging.getLogger(__name__)


def is_gcs_mode() -> bool:
    return (
        os.getenv("OUTPUT_TARGET", "local").lower() == "gcs"
        or os.getenv("DATA_SOURCE", "local").lower() == "gcs"
    )


def _bucket():
    from google.cloud import storage  # type: ignore[import]
    bucket_name = os.getenv("GCS_BUCKET")
    if not bucket_name:
        raise RuntimeError("GCS_BUCKET env var required when OUTPUT_TARGET=gcs")
    return storage.Client().bucket(bucket_name)


def download_db_if_present(local_path: Path) -> bool:
    """Download the existing arf.db from GCS to local_path. Returns True on hit."""
    if not is_gcs_mode():
        return False
    object_name = os.getenv("GCS_DB_OBJECT", "arf.db")
    blob = _bucket().blob(object_name)
    if not blob.exists():
        log.info("No existing %s in GCS — starting fresh", object_name)
        return False
    local_path.parent.mkdir(parents=True, exist_ok=True)
    blob.download_to_filename(str(local_path))
    log.info("Downloaded gs://%s/%s -> %s", blob.bucket.name, object_name, local_path)
    return True


def upload_db(local_path: Path) -> None:
    if not is_gcs_mode():
        return
    object_name = os.getenv("GCS_DB_OBJECT", "arf.db")
    blob = _bucket().blob(object_name)
    blob.upload_from_filename(str(local_path))
    log.info("Uploaded %s -> gs://%s/%s", local_path, blob.bucket.name, object_name)


def upload_artifact(local_path: Path, object_name: str) -> None:
    """Upload an arbitrary file (parquet snapshot, report, etc.)."""
    if not is_gcs_mode():
        return
    prefix = os.getenv("GCS_PREFIX", "").strip("/")
    key = f"{prefix}/{object_name}" if prefix else object_name
    blob = _bucket().blob(key)
    blob.upload_from_filename(str(local_path))
    log.info("Uploaded %s -> gs://%s/%s", local_path, blob.bucket.name, key)
