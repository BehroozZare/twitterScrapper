#!/usr/bin/env bash
set -euo pipefail

# Extract voice (audio) from videos using FFmpeg via transcriber CLI
#
# Usage:
#   bash voice_extract.sh <video_file_or_dir> [extra transcriber.py extract-audio args...]
#
# Examples:
#   bash voice_extract.sh data/
#   bash voice_extract.sh data/ --output ./audio
#   bash voice_extract.sh data/ --no-skip --clean-audio --trim-silence
#
# Notes:
# - Requires FFmpeg on PATH.

SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

if [[ $# -lt 1 ]]; then
  echo "Usage: bash voice_extract.sh <video_file_or_dir> [extra transcriber.py extract-audio args...]"
  echo "Example: bash voice_extract.sh data/ --output ./audio --clean-audio --trim-silence"
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

exec "$PYTHON_BIN" transcriber.py extract-audio "$INPUT_PATH" "$@"
