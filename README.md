# ClipboardDigest (Developing...)

**ClipboardDigest** is a Python tool that runs in the background, monitors your clipboard, and creates a daily summary report. It tracks everything you copy, logs it to a local database, and summarizes your copy activity at the end of each day.

## Features

- Monitors your clipboard
- Stores clipboard entries in SQLite
- Creates daily summaries
- Configurable via `.env` file

## TODO

- [x] Summary worker (LLM)
- [x] Group entries with time proximity
- [x] Insights worker (LLM)
- [ ] Include cool statistics for daily insights
- [ ] Table for daily report
- [ ] Build frontend
