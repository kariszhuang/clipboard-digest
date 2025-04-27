#!/bin/bash

set -euo pipefail

cleanup() {
  if [[ -n "${WORKER_PID:-}" ]]; then
    kill "$WORKER_PID" 2>/dev/null || true
  fi
}

# Load .env variables if exists
if [ -f ".env" ]; then
  set -a
  source .env
  set +a
else
  echo "⚠️  Warning: .env file not found. Skipping."
fi

# Activate virtual environment if exists
if [ -d "venv" ]; then
  source venv/bin/activate
else
  echo "⚠️  Warning: venv not found. Skipping virtualenv activation."
fi

# Add project root to PYTHONPATH 
export PYTHONPATH="${PYTHONPATH:-}:$(pwd)"

# Ensure cleanup on exit
trap cleanup SIGINT SIGTERM EXIT

# Start summary worker
echo "🧠 Starting Summary Worker..."
python3 src/summary_worker.py &
WORKER_PID=$!

# Start clipboard monitor
echo "📋 Starting ClipboardDigest Monitor..."
python3 src/monitor_clipboard.py
