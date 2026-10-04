"""Start-up schema upgrade for the terms-cache columns and the knowledge-base tables.

`Base.metadata.create_all` creates missing tables but never adds columns to an existing one, so a table
created by older code (production Postgres, local SQLite files) would lack them.

Safety rules:
- Only additions: missing columns are added (`ADD COLUMN IF NOT EXISTS` on Postgres) and missing tables
  created (`checkfirst`); nothing is dropped, renamed or rewritten.
- On Postgres each step runs with a short lock_timeout, so start-up never waits behind a long lock.
- Any failure is logged clearly and swallowed: the app still starts. `cache_schema_ready()` and
  `knowledge_base_ready()` then report False, the terms cache is neither read nor written (lookups use
  saved records, discovery and defaults as before) and the knowledge base is skipped.
"""
from __future__ import annotations

import logging
from typing import Any, Dict

from sqlalchemy import inspect, text
from sqlalchemy.engine import Engine

logger = logging.getLogger(__name__)

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
# Tables added by the knowledge base; created separately from the main create_all so a failure here
# cannot stop the rest of start-up.
NEW_TABLES = ("verified_terms", "verified_terms_reviews")
LOCK_TIMEOUT = "5s"

STATUS: Dict[str, Any] = {"ran": False, "cache_ready": False, "knowledge_base_ready": False, "added": {}, "error": None}


def _lock_timeout(conn) -> None:
    if conn.dialect.name == "postgresql":
        conn.execute(text(f"SET LOCAL lock_timeout = '{LOCK_TIMEOUT}'"))


def ensure_columns(engine: Engine) -> Dict[str, list]:
    """Add any missing expected columns; returns {table: [added columns]}."""
    added: Dict[str, list] = {}
    inspector = inspect(engine)
    for table, columns in EXPECTED_COLUMNS.items():
        if not inspector.has_table(table):
            continue
        present = {col["name"] for col in inspector.get_columns(table)}
        missing = [name for name in columns if name not in present]
        if not missing:
            continue
        with engine.begin() as conn:
            _lock_timeout(conn)
            for name in missing:
                pg_type, sqlite_type = columns[name]
                if conn.dialect.name == "postgresql":
                    conn.execute(text(f"ALTER TABLE {table} ADD COLUMN IF NOT EXISTS {name} {pg_type}"))
                else:
                    conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {name} {sqlite_type}"))
        added[table] = missing
    return added


def create_new_tables(engine: Engine) -> list:
    from .db import Base

    created = []
    inspector = inspect(engine)
    for name in NEW_TABLES:
        if inspector.has_table(name):
            continue
        with engine.begin() as conn:
            _lock_timeout(conn)
            Base.metadata.tables[name].create(bind=conn, checkfirst=True)
        created.append(name)
    return created


def check_ready(engine: Engine) -> Dict[str, bool]:
    inspector = inspect(engine)
    cache_ready = inspector.has_table("warranty_terms_cache") and set(EXPECTED_COLUMNS["warranty_terms_cache"]) <= {
        col["name"] for col in inspector.get_columns("warranty_terms_cache")
    }
    kb_ready = all(inspector.has_table(name) for name in NEW_TABLES)
    return {"cache_ready": bool(cache_ready), "knowledge_base_ready": bool(kb_ready)}


def run_startup_upgrade(engine: Engine) -> Dict[str, Any]:
    """Never raises. Updates and returns STATUS."""
    STATUS.update({"ran": True, "added": {}, "error": None})
    try:
        created = create_new_tables(engine)
        added = ensure_columns(engine)
        STATUS["added"] = {**added, **({"tables": created} if created else {})}
    except Exception as exc:  # logged, never fatal
        STATUS["error"] = f"{exc.__class__.__name__}: {str(exc)[:300]}"
    try:
        STATUS.update(check_ready(engine))
    except Exception as exc:
        STATUS.update({"cache_ready": False, "knowledge_base_ready": False})
        STATUS["error"] = STATUS["error"] or f"{exc.__class__.__name__}: {str(exc)[:300]}"
    if STATUS["error"] or not (STATUS["cache_ready"] and STATUS["knowledge_base_ready"]):
        message = (
            "SCHEMA UPGRADE FAILED - app starting anyway; "
            f"terms cache {'on' if STATUS['cache_ready'] else 'OFF (lookups skip the cache)'}, "
            f"knowledge base {'on' if STATUS['knowledge_base_ready'] else 'OFF'}; error: {STATUS['error'] or 'columns/tables missing'}"
        )
        print(message, flush=True)
        logger.error(message)
    elif STATUS["added"]:
        print(f"Schema upgrade: added {STATUS['added']}", flush=True)
    return dict(STATUS)


def cache_schema_ready() -> bool:
    # Before start-up has run (e.g. scripts importing services directly) assume the current schema.
    return STATUS["cache_ready"] if STATUS["ran"] else True


def knowledge_base_ready() -> bool:
    return STATUS["knowledge_base_ready"] if STATUS["ran"] else True
