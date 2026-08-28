#!/usr/bin/env bash
# Capture README screenshots from a running ReplyMind console.
#
#   ./scripts/screenshots.sh [BASE_URL]
#
# Start the app first (REPLYMIND_MODE=demo ./run-ui.sh) and, if you want the
# Mind shown as connected, start minds-service too.
set -euo pipefail

BASE="${1:-http://127.0.0.1:8000}"
# SCALE=2 for retina captures (4x the file size)
OUT="docs/images"
CHROME="$(command -v google-chrome || command -v chromium || command -v chromium-browser)"
mkdir -p "$OUT"

shot() {  # shot <path> <filename> <height>
  "$CHROME" --headless --disable-gpu --hide-scrollbars --no-sandbox \
    --force-device-scale-factor="${SCALE:-1}" --window-size="1440,${3:-1000}" \
    --virtual-time-budget=4000 \
    --screenshot="$OUT/$2" "$BASE$1" >/dev/null 2>&1
  echo "  $2"
}

echo "Capturing from $BASE"
shot "/"                "landing.png"     1180
shot "/overview"        "overview.png"    1120
shot "/signals"         "signals.png"     1120
shot "/comments"        "queue.png"       1050
shot "/agent"           "agent.png"       1050
shot "/memory"          "memory.png"      1120
shot "/activity"        "activity.png"    1050
echo "Done -> $OUT"
