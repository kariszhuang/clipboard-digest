import time
import pyperclip
import os
import hashlib
import sqlite3
from dotenv import load_dotenv
from datetime import datetime, timezone
from pathlib import Path
from src.log_clipboard import log_to_db
from config.env_validate import validate_env

# Load configuration from .env
validate_env()
load_dotenv()

DB_PATH: str = os.getenv("DB_PATH", "data/clipboard.db")
REFRESH_INTERVAL: float = float(os.getenv("REFRESH_INTERVAL", "2"))


def init_db(conn: sqlite3.Connection):
    """Initialize the database with required tables"""
    c = conn.cursor()
    # Enable foreign key constraints
    conn.execute("PRAGMA foreign_keys = ON")

    # Create clipboard table
    c.execute("""
    CREATE TABLE IF NOT EXISTS clipboard (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp TEXT NOT NULL,
        content TEXT NOT NULL,
        summary TEXT,
        type TEXT,
        group_id INTEGER
    )
    """)
    conn.commit()


def get_hash(s: str) -> str:
    """Generate a hash for the given text"""
    return hashlib.sha256(s.encode()).hexdigest()


def get_last_clip_hash(db_path: str) -> str:
    """Get the hash of the most recent clipboard entry"""
    try:
        with sqlite3.connect(db_path) as conn:
            # Initialize the database if needed
            init_db(conn)
            cursor = conn.cursor()
            cursor.execute(
                "SELECT content FROM clipboard ORDER BY timestamp DESC LIMIT 1"
            )
            row = cursor.fetchone()
            return get_hash(row[0].strip()) if row else ""
    except sqlite3.OperationalError as e:
        raise RuntimeError(f"Error accessing clipboard database: {e}")


def check_clipboard(last_hash: str, refresh_interval: float) -> str:
    """
    Check for new clipboard content and log if changed.
    Returns new hash if clipboard changed, otherwise returns the old hash.
    """
    clip: str = pyperclip.paste()
    if not clip.strip():
        return last_hash

    clip_hash = get_hash(clip.strip())
    # Check if the hash of the clipboard content has changed
    if clip_hash != last_hash:
        # debugging output (first 80 chars)
        print(f"Copied: {clip[:80]}{'...' if len(clip) > 80 else ''}")

        # UTC timestamp in ISO format (to second). e.g. 2025-05-08T20:11:29
        ts: str = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S")

        # Log the full original clipboard content to the database
        log_to_db(text=clip, timestamp=ts)
        return clip_hash

    return last_hash


def start_monitoring(db_path: str, refresh_interval: float):
    """Start the clipboard monitoring loop"""

    # Initialize last hash from database
    last_hash = get_last_clip_hash(db_path)

    try:
        while True:
            last_hash = check_clipboard(last_hash, refresh_interval)
            time.sleep(refresh_interval)
    except KeyboardInterrupt:
        print("\nStopped clipboard monitoring. Thanks for using ClipboardDigest!")


def main():
    """Main entry point for the clipboard monitor"""
    # Ensure directory exists
    Path(DB_PATH).parent.mkdir(parents=True, exist_ok=True)

    # Start monitoring clipboard
    start_monitoring(DB_PATH, REFRESH_INTERVAL)


if __name__ == "__main__":
    main()
