import time
import pyperclip
import os
from dotenv import load_dotenv
from datetime import datetime, timezone
from src.log_clipboard import log_to_db

# Load configuration from .env
load_dotenv()
REFRESH_INTERVAL: float = float(os.getenv("REFRESH_INTERVAL", "1"))
LAST: str = ""  # store the last copied text in memory

while True:
    try:
        clip: str = pyperclip.paste()
        if clip != LAST and clip.strip() != "":
            # debugging output (first 80 chars)
            print(f"Copied: {clip[:80]}{'...' if len(clip) > 80 else ''}")

            # UTC timestamp in ISO format
            ts: str = datetime.now(timezone.utc).isoformat()

            # Log the new clipboard content to the database
            log_to_db(text=clip, timestamp=ts)
            LAST = clip

        time.sleep(REFRESH_INTERVAL)

    except KeyboardInterrupt:
        print("\nStopped clipboard monitoring. Thanks for using ClipboardDigest!")
        break
