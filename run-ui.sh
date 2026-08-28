#!/usr/bin/env bash
# Start the ReplyMind console.
set -euo pipefail
export REPLYMIND_MODE="${REPLYMIND_MODE:-demo}"
echo "ReplyMind console -> http://127.0.0.1:${PORT:-8000}  (mode: $REPLYMIND_MODE)"
python -m uvicorn app.review.webapp:app --host 0.0.0.0 --port "${PORT:-8000}"
