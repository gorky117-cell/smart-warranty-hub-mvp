import sqlite3
import os

db_path = os.path.join("data", "app.db")
print(f"Checking warranties table: {os.path.abspath(db_path)}")

conn = sqlite3.connect(db_path)
cursor = conn.cursor()

cursor.execute("PRAGMA table_info(warranties)")
cols = [c[1] for c in cursor.fetchall()]
print(f"Warranty columns: {cols}")

cursor.execute("SELECT id, product_name, brand, purchase_date, model_code, serial_no FROM warranties ORDER BY created_at DESC LIMIT 5")
rows = cursor.fetchall()

print("\n=== Latest 5 Warranties ===")
for row in rows:
    print(f"ID: {row[0]}")
    print(f"  Product: {row[1]}")
    print(f"  Brand: {row[2]}")
    print(f"  Date: {row[3]}")
    print(f"  Model: {row[4]}")
    print(f"  Serial: {row[5]}")
    print("-" * 20)

conn.close()
