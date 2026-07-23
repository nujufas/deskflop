#!/usr/bin/env bash
# Run this machine as the client, with the server positioned to its LEFT
# (i.e. this machine's RIGHT edge borders the server -- pair with server-left.sh
# on the other machine).
# Requires --host; extra args are forwarded, e.g.:
#   ./client-right.sh --host 192.168.1.10 --password secret
set -e
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
exec "$DIR/deskflop.sh" client --edge right "$@"
