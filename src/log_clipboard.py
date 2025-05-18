import sqlite3
import os
from datetime import timezone, datetime
from pathlib import Path
from dotenv import load_dotenv
from config.env_validate import validate_env

# Load configuration from .env
validate_env()
load_dotenv()
DB_PATH: str = os.getenv("DB_PATH", "data/clipboard.db")

# Resolve and ensure data directory exists
db_file: Path = Path(__file__).resolve().parents[1] / DB_PATH
db_file.parent.mkdir(parents=True, exist_ok=True)


def log_to_db(text: str, timestamp: str) -> None:
    """
    Insert a clipboard entry into the DB with a given UTC timestamp.
    """
    conn = sqlite3.connect(str(db_file))

    cursor = conn.cursor()

    # Insert the new entry
    cursor.execute(
        "INSERT INTO clipboard (timestamp, content) VALUES (?, ?)", (timestamp, text)
    )

    conn.commit()
    conn.close()


if __name__ == "__main__":
    # Allow standalone usage: python log_clipboard.py "text" [timestamp]
    import sys

    ts: str = (
        sys.argv[2] if len(sys.argv) > 2 else datetime.now(timezone.utc).isoformat()
    )
    log_to_db(text=sys.argv[1], timestamp=ts)
