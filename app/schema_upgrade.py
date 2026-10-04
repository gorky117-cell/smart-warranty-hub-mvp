"""Add columns that newer code expects to tables that already exist.

`Base.metadata.create_all` creates missing tables but never adds columns to an existing one, so a table
created by older code (production Postgres, local SQLite files) would lack them. Each column is added only
when missing; nothing is dropped or rewritten.
"""
from __future__ import annotations

from typing import Dict

from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine

# table -> column -> (postgres type, sqlite type)
EXPECTED_COLUMNS: Dict[str, Dict[str, tuple]] = {
    "warranty_terms_cache": {
        "model_code": ("TEXT", "TEXT"),
        "product_line": ("TEXT", "TEXT"),
        "source_type": ("TEXT", "TEXT"),
        "confidence": ("DOUBLE PRECISION", "REAL"),
        "grounded": ("BOOLEAN", "BOOLEAN"),
    },
}


def ensure_columns(engine: Engine) -> Dict[str, list]:
    """Add any missing expected columns; returns {table: [added columns]}."""
    added: Dict[str, list] = {}
    inspector = inspect(engine)
    dialect = engine.dialect.name
    for table, columns in EXPECTED_COLUMNS.items():
        if not inspector.has_table(table):
            continue
        present = {col["name"] for col in inspector.get_columns(table)}
        missing = [name for name in columns if name not in present]
        if not missing:
            continue
        with engine.begin() as conn:
            for name in missing:
                pg_type, sqlite_type = columns[name]
                if dialect == "postgresql":
                    conn.execute(text(f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS {name} {pg_type}"))
                else:
                    conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {name} {sqlite_type}"))
        added[table] = missing
    return added
