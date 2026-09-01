from pathlib import Path

import pytest
from sqlalchemy import (
    Column,
    ForeignKey,
    Integer,
    MetaData,
    String,
    Table,
    create_engine,
    select,
)
from sqlalchemy.engine import Engine

from app.scripts.migrate_sqlite_to_postgres import migrate


def _create_schema(path: Path) -> tuple[Engine, Table, Table]:
    engine = create_engine(f"sqlite+pysqlite:///{path}")
    metadata = MetaData()
    parents = Table(
        "parents",
        metadata,
        Column("id", Integer, primary_key=True),
        Column("name", String, nullable=False),
    )
    children = Table(
        "children",
        metadata,
        Column("id", Integer, primary_key=True),
        Column("parent_id", ForeignKey("parents.id"), nullable=False),
    )
    metadata.create_all(engine)
    return engine, parents, children


def test_migrate_copies_tables_in_foreign_key_order(tmp_path: Path) -> None:
    source, source_parents, source_children = _create_schema(tmp_path / "source.db")
    target, target_parents, target_children = _create_schema(tmp_path / "target.db")
    with source.begin() as connection:
        connection.execute(source_parents.insert(), [{"id": 1, "name": "kept"}])
        connection.execute(source_children.insert(), [{"id": 2, "parent_id": 1}])

    copied = migrate(source, target, batch_size=1)

    assert copied == {"parents": 1, "children": 1}
    with target.connect() as connection:
        assert connection.execute(select(target_parents.c.name)).scalar_one() == "kept"
        assert connection.execute(select(target_children.c.parent_id)).scalar_one() == 1


def test_migrate_refuses_nonempty_target(tmp_path: Path) -> None:
    source, source_parents, _ = _create_schema(tmp_path / "source.db")
    target, target_parents, _ = _create_schema(tmp_path / "target.db")
    with source.begin() as connection:
        connection.execute(source_parents.insert(), [{"id": 1, "name": "source"}])
    with target.begin() as connection:
        connection.execute(target_parents.insert(), [{"id": 9, "name": "existing"}])

    with pytest.raises(RuntimeError, match="目标数据库不是空库"):
        migrate(source, target)
