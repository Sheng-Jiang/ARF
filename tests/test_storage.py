"""Unit tests for GCS storage helpers and HMAC interoperability."""
from unittest.mock import MagicMock, patch

import pytest

from arf import storage


@pytest.fixture(autouse=True)
def _reset_env(monkeypatch):
    for key in (
        "OUTPUT_TARGET",
        "DATA_SOURCE",
        "GCS_BUCKET",
        "GCS_DB_OBJECT",
        "GCS_PREFIX",
        "GCS_HMAC_KEY",
        "GCS_HMAC_SECRET",
        "GCS_ACCESS_KEY",
        "GCS_SECRET_KEY",
        "AWS_ACCESS_KEY_ID",
        "AWS_SECRET_ACCESS_KEY",
    ):
        monkeypatch.delenv(key, raising=False)


def test_is_gcs_mode(monkeypatch):
    assert not storage.is_gcs_mode()
    monkeypatch.setenv("OUTPUT_TARGET", "gcs")
    assert storage.is_gcs_mode()
    monkeypatch.setenv("OUTPUT_TARGET", "local")
    monkeypatch.setenv("DATA_SOURCE", "gcs")
    assert storage.is_gcs_mode()


def test_get_hmac_credentials(monkeypatch):
    assert storage._get_hmac_credentials() is None

    monkeypatch.setenv("GCS_HMAC_KEY", "test-key")
    monkeypatch.setenv("GCS_HMAC_SECRET", "test-secret")
    assert storage._get_hmac_credentials() == ("test-key", "test-secret")

    # AWS alias
    monkeypatch.delenv("GCS_HMAC_KEY")
    monkeypatch.delenv("GCS_HMAC_SECRET")
    monkeypatch.setenv("AWS_ACCESS_KEY_ID", "aws-key")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "aws-secret")
    assert storage._get_hmac_credentials() == ("aws-key", "aws-secret")


def test_hmac_headers(monkeypatch):
    monkeypatch.setenv("GCS_HMAC_KEY", "my-key")
    monkeypatch.setenv("GCS_HMAC_SECRET", "my-secret")
    headers = storage._hmac_headers("GET", "test-bucket", "test-obj")
    assert "Authorization" in headers
    assert headers["Authorization"].startswith("AWS my-key:")
    assert "Date" in headers


def test_download_db_hmac(tmp_path, monkeypatch):
    monkeypatch.setenv("OUTPUT_TARGET", "gcs")
    monkeypatch.setenv("GCS_BUCKET", "test-bucket")
    monkeypatch.setenv("GCS_HMAC_KEY", "my-key")
    monkeypatch.setenv("GCS_HMAC_SECRET", "my-secret")

    local_db = tmp_path / "arf.db"

    # 404 test
    with patch("requests.head") as mock_head:
        mock_head.return_value.status_code = 404
        assert not storage.download_db_if_present(local_db)
        assert not local_db.exists()

    # 200 hit test
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.iter_content.return_value = [b"duckdb", b"data"]

    with patch("requests.head") as mock_head, patch("requests.get") as mock_get:
        mock_head.return_value.status_code = 200
        mock_get.return_value.__enter__.return_value = mock_resp
        assert storage.download_db_if_present(local_db)
        assert local_db.exists()
        assert local_db.read_bytes() == b"duckdbdata"


def test_upload_db_hmac(tmp_path, monkeypatch):
    monkeypatch.setenv("OUTPUT_TARGET", "gcs")
    monkeypatch.setenv("GCS_BUCKET", "test-bucket")
    monkeypatch.setenv("GCS_HMAC_KEY", "my-key")
    monkeypatch.setenv("GCS_HMAC_SECRET", "my-secret")

    local_db = tmp_path / "arf.db"
    local_db.write_bytes(b"content to upload")

    with patch("requests.put") as mock_put:
        mock_put.return_value.status_code = 200
        storage.upload_db(local_db)
        assert mock_put.called
        call_url = mock_put.call_args[0][0]
        assert call_url == "https://storage.googleapis.com/test-bucket/arf.db"


def test_upload_artifact_hmac(tmp_path, monkeypatch):
    monkeypatch.setenv("OUTPUT_TARGET", "gcs")
    monkeypatch.setenv("GCS_BUCKET", "test-bucket")
    monkeypatch.setenv("GCS_PREFIX", "prod/snapshots")
    monkeypatch.setenv("GCS_HMAC_KEY", "my-key")
    monkeypatch.setenv("GCS_HMAC_SECRET", "my-secret")

    artifact = tmp_path / "arf_2026-10-21.parquet"
    artifact.write_bytes(b"parquet bytes")

    with patch("requests.put") as mock_put:
        mock_put.return_value.status_code = 200
        storage.upload_artifact(artifact, "arf_2026-10-21.parquet")
        assert mock_put.called
        call_url = mock_put.call_args[0][0]
        assert call_url == "https://storage.googleapis.com/test-bucket/prod/snapshots/arf_2026-10-21.parquet"
