# ClipboardDigest

**ClipboardDigest** is a lightweight Python tool that runs in the background, monitors your clipboard, and creates a daily summary report. It tracks everything you copy, logs it to a local database, and summarizes your copy activity at the end of each day.

## Features

- Monitors your clipboard using Python (`pyperclip`)
- Stores clipboard entries in SQLite
- Creates daily summaries
- Configurable via `.env` file

## Setup

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

## Usage
