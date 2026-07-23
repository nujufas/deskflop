#!/usr/bin/env bash
# Run this machine as the server, with the client positioned to its RIGHT
# (i.e. this machine's RIGHT edge borders the client).
# Extra args are forwarded, e.g.: ./server-right.sh --password secret
set -e
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
exec "$DIR/deskflop.sh" server --edge right "$@"
