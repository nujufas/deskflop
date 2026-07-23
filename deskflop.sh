#!/usr/bin/env bash
# Usage:
#   ./deskflop.sh server [--port 24800] [--edge left|right] [--password SECRET]
#   ./deskflop.sh client --host <server-ip> [--port 24800] [--password SECRET]
set -e
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

PYTHON="python3"
command -v python3 >/dev/null 2>&1 || PYTHON="python"

exec "$PYTHON" "$DIR/deskflop.py" "$@"
