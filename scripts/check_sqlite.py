import sqlite3
import os

db_path = os.path.join("data", "app.db")
print(f"Checking DB at: {os.path.abspath(db_path)}")

if not os.path.exists(db_path):
    print("❌ DB file does not exist!")
else:
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = cursor.fetchall()
        print("Tables found:")
        for t in tables:
            print(f" - {t[0]}")
        
        # Check warranty count if table exists
        if ('warranties',) in tables:
            cursor.execute("SELECT count(*) FROM warranties")
            count = cursor.fetchone()[0]
            print(f"Warranties count: {count}")
            
            # Check pipeline jobs with headers
            cursor.execute("PRAGMA table_info(pipeline_jobs)")
            cols = [c[1] for c in cursor.fetchall()]
            
            
            cursor.execute("SELECT * FROM pipeline_jobs ORDER BY created_at DESC LIMIT 5")
            jobs = cursor.fetchall()
            print(f"Pipeline Jobs count (showing last 5): {len(jobs)}")
            for j in jobs:
                row = dict(zip(cols, j))
                print(f"Job ID: {row.get('id')}")
                print(f"  Warranty ID: {row.get('warranty_id')}")
                print(f"  Status: {row.get('status')}")
                print(f"  Error: {row.get('error')}")
                print(f"  Updated: {row.get('updated_at')}")
                
            print("-" * 20)
            print("Checking Parsed Fields:")
            cursor.execute("SELECT * FROM parsed_fields ORDER BY created_at DESC LIMIT 5")
            fields = cursor.fetchall()
            cursor.execute("PRAGMA table_info(parsed_fields)")
            pcols = [c[1] for c in cursor.fetchall()]
            
            for f in fields:
                row = dict(zip(pcols, f))
                print(f"Field ID: {row.get('id')} (Warranty: {row.get('warranty_id')})")
                print(f"  Product: {row.get('product_name')}")
                print(f"  Brand: {row.get('brand')}")
                print(f"  Date: {row.get('purchase_date')}")
                print("-" * 10)
            
        else:
            print("❌ 'warranties' table NOT found.")
            
        conn.close()
    except Exception as e:
        print(f"Error: {e}")
