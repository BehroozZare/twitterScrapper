#!/usr/bin/env bash
set -euo pipefail

# Generate subtitles (transcription JSON) from extracted voice files
#
# Usage:
#   bash subtitle_generate.sh <audio_file_or_dir> [extra transcriber.py transcribe args...]
#
# Examples:
#   bash subtitle_generate.sh data/
#   bash subtitle_generate.sh data/ --output ./subtitles
#   bash subtitle_generate.sh data/ --update-json
#   bash subtitle_generate.sh data/ --no-skip --model whisper-1
#
# Notes:
# - Loads OpenAI credentials via `.env` (OPENAI_API_KEY). `transcriber.py` loads dotenv.

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

if [[ $# -lt 1 ]]; then
  echo "Usage: bash subtitle_generate.sh <audio_file_or_dir> [extra transcriber.py transcribe args...]"
  echo "Example: bash subtitle_generate.sh data/ --update-json --output ./subtitles"
  exit 2
fi

INPUT_PATH="$1"
shift

PYTHON_BIN="python3"
if [[ -x "./venv/bin/python" ]]; then
  PYTHON_BIN="./venv/bin/python"
elif command -v python3 >/dev/null 2>&1; then
  PYTHON_BIN="python3"
elif command -v python >/dev/null 2>&1; then
  PYTHON_BIN="python"
fi

exec "$PYTHON_BIN" transcriber.py transcribe "$INPUT_PATH" \
  --model "gpt-4o-mini-transcribe" \
  --temperature 0 \
  "$@"
