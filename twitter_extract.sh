#!/usr/bin/env bash
set -euo pipefail

# Run Twitter/X scraping + video download
#
# Usage:
#   bash twitter_extract.sh <profile_url> <start_date> <end_date> [extra scraper.py args...]
#
# Examples:
#   bash twitter_extract.sh "https://x.com/elonmusk" "2024-01-01" "2024-01-31"
#   bash twitter_extract.sh "https://x.com/elonmusk" "2024-01-01" "2024-01-31" --output "./data" --limit 50 --videos-only
#
# Notes:
# - Loads Twitter credentials via `.env` (TWITTER_*). `scraper.py` already calls load_dotenv().

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

if [[ $# -lt 3 ]]; then
  echo "Usage: bash twitter_extract.sh <profile_url> <start_date> <end_date> [extra scraper.py args...]"
  echo "Example: bash twitter_extract.sh \"https://x.com/username\" \"2024-01-01\" \"2024-01-31\" --output ./data --videos-only"
  exit 2
fi

URL="$1"
START_DATE="$2"
END_DATE="$3"
shift 3

PYTHON_BIN="python3"
if [[ -x "./venv/bin/python" ]]; then
  PYTHON_BIN="./venv/bin/python"
elif command -v python3 >/dev/null 2>&1; then
  PYTHON_BIN="python3"
elif command -v python >/dev/null 2>&1; then
  PYTHON_BIN="python"
fi

exec "$PYTHON_BIN" scraper.py --url "$URL" --start-date "$START_DATE" --end-date "$END_DATE" "$@"
