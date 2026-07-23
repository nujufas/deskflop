#!/usr/bin/env bash
# Usage:
#   ./deskflop.sh server [--port 24800] [--edge left|right] [--password SECRET]
#   ./deskflop.sh client --host <server-ip> [--port 24800] [--password SECRET]
#
# Creates/reuses a local .venv next to this script and installs
# requirements.txt into it automatically -- no manual setup needed.
set -e
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="$DIR/.venv"

PYTHON="python3"
command -v python3 >/dev/null 2>&1 || PYTHON="python"

if [ ! -x "$VENV_DIR/bin/python" ]; then
    echo "[deskflop] setting up virtual environment (first run only)..." >&2
    "$PYTHON" -m venv "$VENV_DIR"
fi

VENV_PYTHON="$VENV_DIR/bin/python"
STAMP="$VENV_DIR/.deps-installed"

if [ ! -f "$STAMP" ]; then
    echo "[deskflop] installing dependencies (first run only)..." >&2
    "$VENV_PYTHON" -m pip install --quiet --upgrade pip
    "$VENV_PYTHON" -m pip install --quiet -r "$DIR/requirements.txt"
    touch "$STAMP"
fi

export PYTHONUNBUFFERED=1
exec "$VENV_PYTHON" "$DIR/deskflop.py" "$@"
