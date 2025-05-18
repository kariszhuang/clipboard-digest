# ClipboardDigest (Developing...)

**ClipboardDigest** is a Python tool that runs in the background, monitors your clipboard, and creates a daily summary report. It tracks everything you copy, logs it to a local database, and summarizes your copy activity at the end of each day.

## Features

- **Smart Clipboard Monitoring**: Continuously tracks what you copy with efficient change detection
- **AI-Powered Summaries**: Automatically generates concise summaries of lengthy clipboard content
- **Intelligent Content Grouping**: Groups similar content to avoid duplicate summarization and save API costs
- **Daily Insights**: Creates comprehensive daily reports of your clipboard activity
- **Flexible Configuration**: Easily configurable through `.env` file with sensible defaults
- **Privacy-Focused**: All data remains local in a SQLite database. Supports local LLM (See [`.env.local_llm`](/.env.local_llm))

## TODO

- [x] Summary worker (LLM)
- [x] Group entries with time proximity
- [x] Insights worker (LLM)
- [ ] Include cool statistics for daily insights
- [ ] Table for daily report
- [ ] Build frontend
