import sqlite3
from pathlib import Path


DB_PATH = Path(__file__).resolve().parents[1] / "data" / "app.db"


def ensure_column(conn: sqlite3.Connection, table: str, column: str, col_type: str) -> bool:
    cols = [row[1] for row in conn.execute(f"PRAGMA table_info({table})").fetchall()]
    if column in cols:
        print(f"[ok] {table}.{column} already exists")
        return False
    conn.execute(f"ALTER TABLE {table} ADD COLUMN {column} {col_type}")
    print(f"[add] {table}.{column} ({col_type})")
    return True


def main() -> None:
    if not DB_PATH.exists():
        print(f"[skip] db not found: {DB_PATH}")
        return
    conn = sqlite3.connect(str(DB_PATH))
    try:
        tables = [row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
        if "warranties" not in tables:
            print("[skip] warranties table not found")
            return
        changed = False
        changed |= ensure_column(conn, "warranties", "climate_zone", "TEXT")
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS pipeline_jobs (
                id TEXT PRIMARY KEY,
                warranty_id TEXT NOT NULL,
                artifact_id TEXT,
                source_path TEXT,
                status TEXT,
                detail TEXT,
                error TEXT,
                created_at TEXT,
                updated_at TEXT
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS parsed_fields (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                warranty_id TEXT NOT NULL,
                brand TEXT,
                model_code TEXT,
                product_name TEXT,
                product_category TEXT,
                serial_no TEXT,
                invoice_no TEXT,
                purchase_date TEXT,
                confidence TEXT,
                raw_text TEXT,
                created_at TEXT
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS warranty_terms_cache (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                brand TEXT,
                category TEXT,
                region TEXT,
                source_url TEXT,
                fetched_at TEXT,
                duration_months INTEGER,
                raw_text TEXT,
                terms TEXT,
                exclusions TEXT,
                claim_steps TEXT
            )
            """
        )
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS warranty_summaries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                warranty_id TEXT NOT NULL,
                summary_text TEXT,
                source TEXT,
                created_at TEXT
            )
            """
        )
        if changed:
            conn.commit()
        else:
            print("[ok] no changes needed")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
