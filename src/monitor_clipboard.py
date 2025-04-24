import time
import pyperclip
import os
from dotenv import load_dotenv
from src.log_clipboard import log_to_db  # direct import

load_dotenv()

REFRESH_INTERVAL = int(os.getenv("REFRESH_INTERVAL", "2"))
LAST = "" # store the last copied text

while True:
    try:
        clip = pyperclip.paste()
        if clip != LAST and clip.strip() != "":
            print(f"Copied: {clip[:80]}{'...' if len(clip) > 80 else ''}")
            # Log the new clipboard content to the database
            log_to_db(clip)
            LAST = clip
        time.sleep(REFRESH_INTERVAL)
    except KeyboardInterrupt:
        print("\nStopped clipboard monitoring. Thanks for using ClipboardDigest!")
        break
