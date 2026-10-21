"""GCS storage helpers for pipeline I/O.

The pipeline writes locally first, then optionally syncs artifacts back to GCS
so the webapp (which reads from `gs://<bucket>/arf.db`) sees the new snapshot.

Configuration via env vars:
    OUTPUT_TARGET   "local" (default) or "gcs"
    GCS_BUCKET      bucket name (required when OUTPUT_TARGET=gcs)
    GCS_DB_OBJECT   object key for the DuckDB file (default "arf.db")
    GCS_PREFIX      prefix for snapshot parquet and reports (default "")
"""
import base64
import hashlib
import hmac
import logging
import mimetypes
import os
from datetime import UTC, datetime
from pathlib import Path

import requests
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

log = logging.getLogger(__name__)

DEFAULT_GCS_ENDPOINT = "https://storage.googleapis.com"


def is_gcs_mode() -> bool:
    return (
        os.getenv("OUTPUT_TARGET", "local").lower() == "gcs"
        or os.getenv("DATA_SOURCE", "local").lower() == "gcs"
    )


def _get_hmac_credentials() -> tuple[str, str] | None:
    """Return (access_key, secret_key) if GCS HMAC interoperability credentials are set.

    Only GCS-specific names are honoured. Ambient ``AWS_ACCESS_KEY_ID`` /
    ``AWS_SECRET_ACCESS_KEY`` values are deliberately ignored: a developer with
    AWS credentials but GCS mode enabled would otherwise switch this module
    onto an HMAC path with the wrong key and fail (or, worse, start from a
    fresh DB) instead of using Application Default Credentials.
    """
    key = os.getenv("GCS_HMAC_KEY") or os.getenv("GCS_ACCESS_KEY")
    secret = os.getenv("GCS_HMAC_SECRET") or os.getenv("GCS_SECRET_KEY")
    if key and secret and key.strip() and secret.strip():
        return key.strip(), secret.strip()
    return None


def _get_bucket_name() -> str:
    bucket_name = os.getenv("GCS_BUCKET")
    if not bucket_name:
        raise RuntimeError("GCS_BUCKET env var required when OUTPUT_TARGET=gcs")
    return bucket_name.strip()


def _hmac_headers(
    method: str,
    bucket: str,
    object_name: str,
    content_type: str = "",
    content_md5: str = "",
) -> dict[str, str]:
    """Generate AWS/GCS HMAC-SHA1 Authorization headers (S3 V2 interoperability)."""
    creds = _get_hmac_credentials()
    if not creds:
        raise RuntimeError("GCS HMAC credentials not configured")
    access_key, secret_key = creds
    now_str = datetime.now(UTC).strftime("%a, %d %b %Y %H:%M:%S GMT")
    clean_name = object_name.lstrip("/")
    string_to_sign = f"{method}\n{content_md5}\n{content_type}\n{now_str}\n/{bucket}/{clean_name}"
    signature = base64.b64encode(
        hmac.new(secret_key.encode("utf-8"), string_to_sign.encode("utf-8"), hashlib.sha1).digest()
    ).decode("utf-8")
    headers = {
        "Date": now_str,
        "Authorization": f"AWS {access_key}:{signature}",
    }
    if content_type:
        headers["Content-Type"] = content_type
    return headers


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=8),
    retry=retry_if_exception_type(requests.RequestException),
    reraise=True,
)
def _hmac_download_file(bucket: str, object_name: str, local_path: Path) -> bool:
    endpoint = os.getenv("GCS_ENDPOINT", DEFAULT_GCS_ENDPOINT).rstrip("/")
    clean_name = object_name.lstrip("/")
    url = f"{endpoint}/{bucket}/{clean_name}"

    head_headers = _hmac_headers("HEAD", bucket, clean_name)
    with requests.head(url, headers=head_headers, timeout=10) as head_resp:
        if head_resp.status_code == 404:
            log.info("No existing %s in GCS — starting fresh", object_name)
            return False
        if head_resp.status_code in (401, 403):
            # Never fall through to "start fresh" on an auth failure: the run
            # would later upload a brand-new DB over the real one.
            raise RuntimeError(
                f"GCS HEAD {url} denied ({head_resp.status_code}); "
                "check GCS_HMAC_KEY/GCS_HMAC_SECRET — refusing to start a fresh DB"
            )
        if head_resp.status_code not in (200, 206):
            head_resp.raise_for_status()
            raise requests.RequestException(
                f"Unexpected GCS HEAD status {head_resp.status_code} for {url}"
            )

    # Stream to a sibling temp file and swap atomically, so a dropped transfer
    # cannot leave a truncated DuckDB in place of the previous good copy.
    local_path.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = local_path.with_name(local_path.name + ".part")
    try:
        get_headers = _hmac_headers("GET", bucket, clean_name)
        with requests.get(url, headers=get_headers, stream=True, timeout=60) as resp:
            resp.raise_for_status()
            with open(tmp_path, "wb") as f:
                for chunk in resp.iter_content(chunk_size=65536):
                    if chunk:
                        f.write(chunk)
        os.replace(tmp_path, local_path)
    finally:
        tmp_path.unlink(missing_ok=True)
    log.info("Downloaded gs://%s/%s -> %s (via HMAC)", bucket, clean_name, local_path)
    return True


@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=8),
    retry=retry_if_exception_type(requests.RequestException),
    reraise=True,
)
def _hmac_upload_file(local_path: Path, bucket: str, object_name: str) -> None:
    endpoint = os.getenv("GCS_ENDPOINT", DEFAULT_GCS_ENDPOINT).rstrip("/")
    clean_name = object_name.lstrip("/")
    url = f"{endpoint}/{bucket}/{clean_name}"

    content_type, _ = mimetypes.guess_type(str(local_path))
    content_type = content_type or "application/octet-stream"

    headers = _hmac_headers("PUT", bucket, clean_name, content_type=content_type)
    with open(local_path, "rb") as f:
        resp = requests.put(url, data=f, headers=headers, timeout=120)
    resp.raise_for_status()
    log.info("Uploaded %s -> gs://%s/%s (via HMAC)", local_path, bucket, clean_name)


def _bucket():
    from google.cloud import storage  # type: ignore[import]
    bucket_name = _get_bucket_name()
    return storage.Client().bucket(bucket_name)


def download_db_if_present(local_path: Path) -> bool:
    """Download the existing arf.db from GCS to local_path. Returns True on hit."""
    if not is_gcs_mode():
        return False
    object_name = os.getenv("GCS_DB_OBJECT", "arf.db")
    bucket_name = _get_bucket_name()

    if _get_hmac_credentials():
        return _hmac_download_file(bucket_name, object_name, local_path)

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
    bucket_name = _get_bucket_name()

    if _get_hmac_credentials():
        _hmac_upload_file(local_path, bucket_name, object_name)
        return

    blob = _bucket().blob(object_name)
    blob.upload_from_filename(str(local_path))
    log.info("Uploaded %s -> gs://%s/%s", local_path, blob.bucket.name, object_name)


def upload_artifact(local_path: Path, object_name: str) -> None:
    """Upload an arbitrary file (parquet snapshot, report, etc.)."""
    if not is_gcs_mode():
        return
    prefix = os.getenv("GCS_PREFIX", "").strip("/")
    key = f"{prefix}/{object_name}" if prefix else object_name
    bucket_name = _get_bucket_name()

    if _get_hmac_credentials():
        _hmac_upload_file(local_path, bucket_name, key)
        return

    blob = _bucket().blob(key)
    blob.upload_from_filename(str(local_path))
    log.info("Uploaded %s -> gs://%s/%s", local_path, blob.bucket.name, key)
