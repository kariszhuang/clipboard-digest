import sqlite3
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv
import os

load_dotenv()
db_path = Path(__file__).resolve().parents[1] / "data" / "clipboard.db"
db_path.parent.mkdir(parents=True, exist_ok=True)

def log_to_db(text: str):
    conn = sqlite3.connect(str(db_path))
    c = conn.cursor()

    c.execute("""
    CREATE TABLE IF NOT EXISTS clipboard (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp TEXT NOT NULL,
        content TEXT NOT NULL
    )
    """)
    
    c.execute("INSERT INTO clipboard (timestamp, content) VALUES (?, ?)",
              (datetime.now().isoformat(), text))

    conn.commit()
    conn.close()

if __name__ == "__main__":
    import sys
    log_to_db(sys.argv[1])
