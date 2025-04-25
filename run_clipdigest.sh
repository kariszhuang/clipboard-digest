#!/bin/bash

# Safely load .env variables
set -a
[ -f .env ] && source .env
set +a

# Activate virtualenv
if [ -d "venv" ]; then
  source venv/bin/activate
fi

# Add project root to PYTHONPATH
export PYTHONPATH=$(pwd)

# Start clipboard monitor only
echo "📋 Starting ClipboardDigest (logger only)..."
python3 src/monitor_clipboard.py
