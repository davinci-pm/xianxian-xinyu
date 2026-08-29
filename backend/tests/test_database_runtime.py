import sqlite3
from pathlib import Path
from typing import Any

from botocore.exceptions import ClientError

from app.core import config as config_module
from app.core.config import get_settings
from app.services import database_runtime


class FakeS3:
    def __init__(self) -> None:
        self.objects: dict[str, bytes] = {}
        self.metadata: dict[str, dict[str, str]] = {}

    def upload_file(
        self,
        filename: str,
        _bucket: str,
        key: str,
        ExtraArgs: dict[str, Any] | None = None,
    ) -> None:
        assert ExtraArgs is not None
        assert ExtraArgs["ServerSideEncryption"] == "AES256"
        self.objects[key] = Path(filename).read_bytes()
        self.metadata[key] = dict(ExtraArgs["Metadata"])

    def download_file(self, _bucket: str, key: str, filename: str) -> None:
        Path(filename).write_bytes(self.objects[key])

    def list_objects_v2(self, *, Bucket: str, Prefix: str) -> dict[str, Any]:
        assert Bucket == "test-bucket"
        return {"Contents": [{"Key": key} for key in self.objects if key.startswith(Prefix)]}

    def head_object(self, *, Bucket: str, Key: str) -> dict[str, Any]:
        assert Bucket == "test-bucket"
        if Key not in self.objects:
            raise ClientError({"Error": {"Code": "404"}}, "HeadObject")
        return {"Metadata": self.metadata.get(Key, {})}

    def delete_objects(self, **_kwargs: Any) -> None:
        raise AssertionError("测试数据未超过保留数量，不应删除")


def test_sqlite_backup_and_restore_round_trip(
    tmp_path: Path, monkeypatch: Any
) -> None:
    database_path = tmp_path / "runtime.db"
    with sqlite3.connect(database_path) as connection:
        connection.execute("CREATE TABLE sample (value TEXT NOT NULL)")
        connection.execute("INSERT INTO sample VALUES ('kept')")

    monkeypatch.setenv("DATABASE_URL", f"sqlite+pysqlite:///{database_path}")
    monkeypatch.setenv("STORAGE_PROVIDER", "s3")
    monkeypatch.setenv("S3_ENDPOINT", "https://example.invalid")
    monkeypatch.setenv("S3_ACCESS_KEY", "test-ak")
    monkeypatch.setenv("S3_SECRET_KEY", "test-sk")
    monkeypatch.setenv("S3_BUCKET", "test-bucket")
    get_settings.cache_clear()
    fake = FakeS3()
    monkeypatch.setattr(database_runtime, "_s3_client", lambda: fake)

    try:
        version_key = database_runtime.backup_database()
        assert version_key is not None
        assert "db/persona-chat.db" in fake.objects

        database_path.unlink()
        assert database_runtime.restore_database_if_needed() is True
        with sqlite3.connect(database_path) as restored:
            assert restored.execute("SELECT value FROM sample").fetchone() == ("kept",)
    finally:
        get_settings.cache_clear()


def test_older_instance_cannot_overwrite_newer_backup(
    tmp_path: Path, monkeypatch: Any
) -> None:
    database_path = tmp_path / "runtime.db"
    with sqlite3.connect(database_path) as connection:
        connection.execute("CREATE TABLE sample (value TEXT NOT NULL)")
        connection.execute("INSERT INTO sample VALUES ('stale')")

    monkeypatch.setenv("DATABASE_URL", f"sqlite+pysqlite:///{database_path}")
    monkeypatch.setenv("STORAGE_PROVIDER", "s3")
    monkeypatch.setenv("S3_ENDPOINT", "https://example.invalid")
    monkeypatch.setenv("S3_ACCESS_KEY", "test-ak")
    monkeypatch.setenv("S3_SECRET_KEY", "test-sk")
    monkeypatch.setenv("S3_BUCKET", "test-bucket")
    get_settings.cache_clear()
    fake = FakeS3()
    fake.objects["db/persona-chat.db"] = b"newer"
    fake.metadata["db/persona-chat.db"] = {
        "instance-generation": "20260829T010001.000000Z-newer"
    }
    monkeypatch.setattr(
        database_runtime, "INSTANCE_GENERATION", "20260829T010000.000000Z-older"
    )
    monkeypatch.setattr(database_runtime, "_s3_client", lambda: fake)

    try:
        assert database_runtime.backup_database() is None
        assert fake.objects["db/persona-chat.db"] == b"newer"
    finally:
        get_settings.cache_clear()


def test_production_s3_uses_deployment_scoped_database_path(
    tmp_path: Path, monkeypatch: Any
) -> None:
    generation_file = tmp_path / "deployment-generation.txt"
    generation_file.write_text("revision-abc123", encoding="utf-8")
    monkeypatch.setattr(config_module, "DEPLOYMENT_GENERATION_FILE", generation_file)
    monkeypatch.setenv("APP_ENV", "production")
    monkeypatch.setenv("STORAGE_PROVIDER", "s3")
    monkeypatch.setenv("DATABASE_URL", "sqlite+pysqlite:////tmp/data/persona-chat.db")
    get_settings.cache_clear()

    try:
        assert get_settings().database_url == (
            "sqlite+pysqlite:////tmp/data/revision-abc123/persona-chat.db"
        )
    finally:
        get_settings.cache_clear()
