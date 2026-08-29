import asyncio
import logging
import os
import shutil
import sqlite3
from contextlib import suppress
from datetime import UTC, datetime
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any
from uuid import uuid4

import boto3
from alembic.config import Config
from botocore.client import Config as BotoConfig
from botocore.exceptions import ClientError
from sqlalchemy.engine import make_url

from alembic import command
from app.core.config import BACKEND_ROOT, get_settings

logger = logging.getLogger(__name__)
INSTANCE_GENERATION = f"{datetime.now(UTC).strftime('%Y%m%dT%H%M%S.%fZ')}-{uuid4().hex}"


def database_path() -> Path | None:
    url = make_url(get_settings().database_url)
    if not url.drivername.startswith("sqlite") or not url.database or url.database == ":memory:":
        return None
    return Path(url.database).resolve()


def _s3_client() -> Any:
    settings = get_settings()
    if not all(
        [settings.s3_endpoint, settings.s3_access_key, settings.s3_secret_key, settings.s3_bucket]
    ):
        raise RuntimeError("TOS 备份已启用，但 S3/TOS 配置不完整")
    return boto3.client(
        "s3",
        endpoint_url=settings.s3_endpoint,
        aws_access_key_id=settings.s3_access_key,
        aws_secret_access_key=settings.s3_secret_key,
        region_name=settings.s3_region,
        config=BotoConfig(signature_version="s3v4", s3={"addressing_style": "virtual"}),
    )


def _integrity_check(path: Path) -> None:
    with sqlite3.connect(path) as connection:
        result = connection.execute("PRAGMA integrity_check").fetchone()
    if result is None or result[0] != "ok":
        raise RuntimeError("SQLite 完整性校验失败")


def restore_database_if_needed() -> bool:
    settings = get_settings()
    path = database_path()
    if path is None or path.exists() or settings.storage_provider != "s3":
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    client = _s3_client()
    with NamedTemporaryFile(dir=path.parent, prefix="restore-", suffix=".db", delete=False) as temp:
        temp_path = Path(temp.name)
    try:
        client.download_file(settings.s3_bucket, settings.db_backup_key, str(temp_path))
        _integrity_check(temp_path)
        os.replace(temp_path, path)
        logger.info("database_restore_completed")
        return True
    except ClientError as exc:
        error_code = str(exc.response.get("Error", {}).get("Code", ""))
        if error_code in {"404", "NoSuchKey", "NoSuchBucket"}:
            logger.warning("database_backup_not_found")
            return False
        raise
    finally:
        with suppress(FileNotFoundError):
            temp_path.unlink()


def run_migrations() -> None:
    config = Config(str(BACKEND_ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(BACKEND_ROOT / "alembic"))
    command.upgrade(config, "head")


def prepare_database() -> None:
    path = database_path()
    if path is not None:
        path.parent.mkdir(parents=True, exist_ok=True)
    restored = restore_database_if_needed()
    settings = get_settings()
    if (
        path is not None
        and not path.exists()
        and not restored
        and settings.database_bootstrap_path.is_file()
    ):
        shutil.copy2(settings.database_bootstrap_path, path)
        _integrity_check(path)
        logger.info("database_bootstrap_copied")
    run_migrations()


def backup_database() -> str | None:
    settings = get_settings()
    source_path = database_path()
    if settings.storage_provider != "s3" or source_path is None or not source_path.exists():
        return None
    client = _s3_client()
    assert settings.s3_bucket is not None
    remote_generation = _remote_instance_generation(
        client, settings.s3_bucket, settings.db_backup_key
    )
    if remote_generation > INSTANCE_GENERATION:
        logger.warning("database_backup_skipped_newer_instance")
        return None
    with NamedTemporaryFile(
        dir=source_path.parent, prefix="backup-", suffix=".db", delete=False
    ) as temp:
        snapshot_path = Path(temp.name)
    try:
        with sqlite3.connect(source_path) as source, sqlite3.connect(snapshot_path) as target:
            source.backup(target)
        _integrity_check(snapshot_path)
        timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
        base = settings.db_backup_key.rsplit(".", 1)[0]
        version_key = f"{base}/versions/{timestamp}.db"
        extra = {
            "ServerSideEncryption": "AES256",
            "Metadata": {"instance-generation": INSTANCE_GENERATION},
        }
        client.upload_file(str(snapshot_path), settings.s3_bucket, version_key, ExtraArgs=extra)
        client.upload_file(
            str(snapshot_path), settings.s3_bucket, settings.db_backup_key, ExtraArgs=extra
        )
        _prune_old_versions(client, f"{base}/versions/")
        logger.info("database_backup_completed", extra={"backup_key": version_key})
        return version_key
    finally:
        with suppress(FileNotFoundError):
            snapshot_path.unlink()


def _remote_instance_generation(client: Any, bucket: str, key: str) -> str:
    try:
        response = client.head_object(Bucket=bucket, Key=key)
    except ClientError as exc:
        error_code = str(exc.response.get("Error", {}).get("Code", ""))
        if error_code in {"404", "NoSuchKey", "NotFound"}:
            return ""
        raise
    metadata = response.get("Metadata", {})
    return str(metadata.get("instance-generation", ""))


def _prune_old_versions(client: Any, prefix: str) -> None:
    settings = get_settings()
    response = client.list_objects_v2(Bucket=settings.s3_bucket, Prefix=prefix)
    objects = sorted(response.get("Contents", []), key=lambda item: item["Key"], reverse=True)
    expired = objects[settings.db_backup_keep_versions :]
    if expired:
        client.delete_objects(
            Bucket=settings.s3_bucket,
            Delete={"Objects": [{"Key": item["Key"]} for item in expired], "Quiet": True},
        )


async def backup_loop(stop_event: asyncio.Event) -> None:
    interval = max(get_settings().db_backup_interval_seconds, 60)
    while True:
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=interval)
            return
        except TimeoutError:
            try:
                await asyncio.to_thread(backup_database)
            except Exception:
                logger.exception("database_backup_failed")
