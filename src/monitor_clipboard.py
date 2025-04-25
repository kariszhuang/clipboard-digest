import time
import pyperclip
import os
import hashlib
import sqlite3
from dotenv import load_dotenv
from datetime import datetime, timezone
from src.log_clipboard import log_to_db

# Load configuration from .env
load_dotenv()
REFRESH_INTERVAL: float = float(os.getenv("REFRESH_INTERVAL", "2"))
DB_PATH: str = os.getenv("DB_PATH", "data/clipboard.db")


def get_hash(s: str) -> str:
    return hashlib.sha256(s.encode()).hexdigest()


def get_last_clip_hash(db_path: str) -> str:
    if not os.path.exists(db_path):
        return ""

    try:
        with sqlite3.connect(db_path) as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT content FROM clipboard ORDER BY timestamp DESC LIMIT 1"
            )
            row = cursor.fetchone()
            return get_hash(row[0].strip()) if row else ""
    except sqlite3.OperationalError as e:
        # table doesn't exist
        if "no such table" in str(e).lower():
            return ""
        raise


# Initialize LAST_HASH from the most recent clipboard entry (based on its stripped content)
LAST_HASH: str = get_last_clip_hash(DB_PATH)


while True:
    try:
        clip: str = pyperclip.paste()
        if not clip.strip():
            time.sleep(REFRESH_INTERVAL)
            continue

        clip_hash = get_hash(clip.strip())
        # Check if the hash of the clipboard content has changed
        if get_hash(clip.strip()) != LAST_HASH:
            # debugging output (first 80 chars)
            print(f"Copied: {clip[:80]}{'...' if len(clip) > 80 else ''}")

            # UTC timestamp in ISO format
            ts: str = datetime.now(timezone.utc).isoformat()

            # Log the full original clipboard content to the database
            log_to_db(text=clip, timestamp=ts)
            LAST_HASH = clip_hash

        time.sleep(REFRESH_INTERVAL)

    except KeyboardInterrupt:
        print("\nStopped clipboard monitoring. Thanks for using ClipboardDigest!")
        break
