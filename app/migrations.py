"""A tiny, safe schema updater for the local SQLite database.

`Base.metadata.create_all` creates MISSING TABLES but never changes tables that already
exist. When a model gains a new column, an older database file would then fail with
"no such column". `add_missing_columns` adds those columns, keeps every existing row,
and never drops or renames anything.

It only handles new columns. Renames, type changes and deletions still need a real
migration tool such as Alembic.
"""

from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine

from .database import Base


def add_missing_columns(engine: Engine) -> list[str]:
    """Add model columns that are missing from existing tables. Returns what was added."""
    added: list[str] = []
    inspector = inspect(engine)
    with engine.begin() as conn:
        for table in Base.metadata.sorted_tables:
            if not inspector.has_table(table.name):
                continue  # create_all will build it from scratch
            existing = {col["name"] for col in inspector.get_columns(table.name)}
            for col in table.columns:
                if col.name in existing:
                    continue
                ddl = (
                    f'ALTER TABLE "{table.name}" ADD COLUMN "{col.name}" '
                    f"{col.type.compile(engine.dialect)}"
                )
                if col.server_default is not None:
                    ddl += f" DEFAULT '{col.server_default.arg}'"
                elif not col.nullable and not col.primary_key:
                    raise RuntimeError(
                        f"Cannot add required column {table.name}.{col.name} without a "
                        "server_default. Give it one, or use a real migration."
                    )
                conn.execute(text(ddl))
                added.append(f"{table.name}.{col.name}")
    return added
