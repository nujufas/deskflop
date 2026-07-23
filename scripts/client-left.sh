#!/usr/bin/env bash
# Run this machine as the client, with the server positioned to its RIGHT
# (i.e. this machine's LEFT edge borders the server -- pair with server-right.sh
# on the other machine).
# Requires --host; extra args are forwarded, e.g.:
#   ./client-left.sh --host 192.168.1.10 --password secret
set -e
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
exec "$DIR/deskflop.sh" client --edge left "$@"
