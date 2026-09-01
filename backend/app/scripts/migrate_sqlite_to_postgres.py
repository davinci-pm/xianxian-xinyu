import argparse
import os
from collections.abc import Iterable
from pathlib import Path
from typing import Any

from alembic.config import Config
from sqlalchemy import MetaData, Table, create_engine, func, insert, select
from sqlalchemy.engine import Connection, Engine, make_url

from alembic import command
from app.core.config import BACKEND_ROOT, get_settings


def _database_url_from_env(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise RuntimeError(f"环境变量 {name} 未配置")
    url = make_url(value)
    if url.get_backend_name() != "postgresql":
        raise RuntimeError(f"环境变量 {name} 必须是 PostgreSQL 连接串")
    return value


def _sqlite_url(path: Path) -> str:
    resolved = path.expanduser().resolve()
    if not resolved.is_file():
        raise FileNotFoundError(f"SQLite 文件不存在：{resolved}")
    return f"sqlite+pysqlite:///{resolved}"


def _run_target_migrations(target_url: str) -> None:
    previous = os.environ.get("DATABASE_URL")
    os.environ["DATABASE_URL"] = target_url
    get_settings.cache_clear()
    try:
        config = Config(str(BACKEND_ROOT / "alembic.ini"))
        config.set_main_option("script_location", str(BACKEND_ROOT / "alembic"))
        command.upgrade(config, "head")
    finally:
        if previous is None:
            os.environ.pop("DATABASE_URL", None)
        else:
            os.environ["DATABASE_URL"] = previous
        get_settings.cache_clear()


def _application_tables(metadata: MetaData) -> list[Table]:
    return [table for table in metadata.sorted_tables if table.name != "alembic_version"]


def _table_count(connection: Connection, table: Table) -> int:
    return int(connection.execute(select(func.count()).select_from(table)).scalar_one())


def _batched(rows: Iterable[dict[str, Any]], size: int) -> Iterable[list[dict[str, Any]]]:
    batch: list[dict[str, Any]] = []
    for row in rows:
        batch.append(row)
        if len(batch) >= size:
            yield batch
            batch = []
    if batch:
        yield batch


def migrate(
    source_engine: Engine, target_engine: Engine, *, batch_size: int = 500
) -> dict[str, int]:
    source_metadata = MetaData()
    target_metadata = MetaData()
    source_metadata.reflect(bind=source_engine)
    target_metadata.reflect(bind=target_engine)

    copied: dict[str, int] = {}
    with source_engine.connect() as source, target_engine.begin() as target:
        target_tables = _application_tables(target_metadata)
        nonempty = [
            table.name for table in target_tables if _table_count(target, table) > 0
        ]
        if nonempty:
            raise RuntimeError(
                "目标数据库不是空库，已停止迁移：" + ", ".join(sorted(nonempty))
            )

        for target_table in target_tables:
            source_table = source_metadata.tables.get(target_table.name)
            if source_table is None:
                copied[target_table.name] = 0
                continue
            common_columns = [
                column.name
                for column in target_table.columns
                if column.name in source_table.columns
            ]
            query = select(*(source_table.c[name] for name in common_columns))
            rows = (dict(row) for row in source.execute(query).mappings())
            count = 0
            for batch in _batched(rows, batch_size):
                target.execute(insert(target_table), batch)
                count += len(batch)
            copied[target_table.name] = count

    with target_engine.connect() as target:
        mismatches = {
            table.name: (copied.get(table.name, 0), _table_count(target, table))
            for table in _application_tables(target_metadata)
            if copied.get(table.name, 0) != _table_count(target, table)
        }
    if mismatches:
        raise RuntimeError(f"迁移后行数校验失败：{mismatches}")
    return copied


def main() -> None:
    parser = argparse.ArgumentParser(description="将现有 SQLite 数据迁移到空 PostgreSQL 数据库")
    parser.add_argument("--source", type=Path, required=True, help="SQLite 快照文件")
    parser.add_argument(
        "--target-env",
        default="PRODUCTION_DATABASE_URL",
        help="保存 PostgreSQL 连接串的环境变量名",
    )
    parser.add_argument("--batch-size", type=int, default=500)
    parser.add_argument("--execute", action="store_true", help="确认执行写入；默认只检查")
    args = parser.parse_args()
    if args.batch_size < 1:
        raise ValueError("batch-size 必须大于 0")

    source_url = _sqlite_url(args.source)
    target_url = _database_url_from_env(args.target_env)
    source_engine = create_engine(source_url)
    target_engine = create_engine(target_url, pool_pre_ping=True)
    with source_engine.connect() as source:
        source_tables = MetaData()
        source_tables.reflect(bind=source)
        summary = {
            table.name: _table_count(source, table)
            for table in _application_tables(source_tables)
        }
    print(f"源数据库检查完成：{len(summary)} 张表，{sum(summary.values())} 行")
    if not args.execute:
        print("未写入目标数据库；确认后增加 --execute")
        return

    _run_target_migrations(target_url)
    copied = migrate(source_engine, target_engine, batch_size=args.batch_size)
    print(f"迁移完成：{len(copied)} 张表，{sum(copied.values())} 行，行数校验通过")


if __name__ == "__main__":
    main()
