#!/usr/bin/env bash
# Fetch sample tests for a problem via Competitive Companion.
#   mkprob.sh a        -> writes a.cpp:tests in the current directory
#   mkprob.sh          -> names files a, b, c, ... (useful for "parse all")
set -uo pipefail

here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
exec python3 "$here/makesamples.py" "$@"
