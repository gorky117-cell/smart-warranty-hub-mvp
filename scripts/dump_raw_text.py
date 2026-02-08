import sqlite3
import os

db_path = os.path.join("data", "app.db")
print(f"Checking raw_text in parsed_fields: {os.path.abspath(db_path)}")

conn = sqlite3.connect(db_path)
cursor = conn.cursor()

cursor.execute("SELECT id, warranty_id, raw_text FROM parsed_fields ORDER BY id DESC LIMIT 5")
rows = cursor.fetchall()

for row in rows:
    fid, wid, raw = row
    print(f"\n=== Field ID: {fid}, Warranty: {wid} ===")
    if raw:
        print(f"RAW TEXT (first 500 chars):\n{raw[:500]}")
    else:
        print("RAW TEXT: (empty or None)")

conn.close()
