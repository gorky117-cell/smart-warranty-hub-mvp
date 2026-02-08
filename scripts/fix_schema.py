import sqlite3
import os

db_path = os.path.join("data", "app.db")
print(f"Migrating DB at: {os.path.abspath(db_path)}")

if not os.path.exists(db_path):
    print("❌ DB file does not exist!")
else:
    try:
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # Check current columns
        cursor.execute("PRAGMA table_info(warranties)")
        cols = [c[1] for c in cursor.fetchall()]
        print(f"Current columns: {cols}")
        
        # Fix: Add region_code if missing
        if "region_code" not in cols:
            print("Adding missing column 'region_code'...")
            cursor.execute("ALTER TABLE warranties ADD COLUMN region_code VARCHAR")
            print("✅ Added 'region_code'.")
        else:
            print("✅ 'region_code' already exists.")

        # Fix: Add other potentially missing fields from recent models
        potential_missing = [
             "oem_risk_factor", "brand_reliability_score", 
             "behaviour_score", "care_score", "response_speed_score",
             "climate_zone"
        ]
        
        for col in potential_missing:
            if col not in cols:
                 print(f"Adding missing column '{col}'...")
                 # Sqlite add column requires type info usually, FLOAT/VARCHAR is safe enough
                 entry_type = "FLOAT" if "score" in col or "factor" in col else "VARCHAR"
                 cursor.execute(f"ALTER TABLE warranties ADD COLUMN {col} {entry_type}")
                 print(f"✅ Added '{col}'.")

        conn.commit()
        conn.close()
        print("Migration complete.")
        
    except Exception as e:
        print(f"❌ Migration Error: {e}")
