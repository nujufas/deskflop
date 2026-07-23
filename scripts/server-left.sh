#!/usr/bin/env bash
# Run this machine as the server, with the client positioned to its LEFT
# (i.e. this machine's LEFT edge borders the client).
# Extra args are forwarded, e.g.: ./server-left.sh --password secret
set -e
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
exec "$DIR/deskflop.sh" server --edge left "$@"
