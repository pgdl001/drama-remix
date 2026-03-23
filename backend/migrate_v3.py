"""Database migration V3: Add interspersed narration + voice cloning fields."""

import sqlite3
import sys
from pathlib import Path

DB_PATH = Path(__file__).parent / "data" / "drama_remix.db"


def migrate():
    if not DB_PATH.exists():
        print(f"Database not found: {DB_PATH}")
        sys.exit(1)

    conn = sqlite3.connect(str(DB_PATH))
    cur = conn.cursor()

    # -- remix_tasks: add narration_ratio and voice_sample_id --
    migrations = [
        ("remix_tasks", "narration_ratio", "REAL DEFAULT 30.0"),
        ("remix_tasks", "voice_sample_id", "VARCHAR(36) DEFAULT NULL"),
    ]

    for table, column, col_def in migrations:
        try:
            cur.execute(f"ALTER TABLE {table} ADD COLUMN {column} {col_def}")
            print(f"[OK] Added {table}.{column}")
        except sqlite3.OperationalError as e:
            if "duplicate column" in str(e).lower():
                print(f"[SKIP] {table}.{column} already exists")
            else:
                print(f"[ERROR] {table}.{column}: {e}")

    # -- Create voice_samples table --
    cur.execute("""
        CREATE TABLE IF NOT EXISTS voice_samples (
            id VARCHAR(36) PRIMARY KEY,
            name VARCHAR(200) NOT NULL,
            file_path TEXT NOT NULL,
            duration REAL DEFAULT 0.0,
            prompt_text TEXT DEFAULT '',
            user_id VARCHAR(36) NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP
        )
    """)
    print("[OK] voice_samples table ready")

    conn.commit()
    conn.close()
    print("[DONE] Migration V3 complete")


if __name__ == "__main__":
    migrate()
