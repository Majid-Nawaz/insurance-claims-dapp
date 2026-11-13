#!/usr/bin/env bash
# Creates the Python virtual environment if needed, installs the dependencies
# and runs the automated test suite against Ganache.
#
# Usage:
#   ./scripts/test.sh [RPC_URL]      (default RPC_URL: http://127.0.0.1:7545)

set -euo pipefail

cd "$(dirname "$0")/.."
export GANACHE_RPC="${1:-http://127.0.0.1:7545}"

# Find a working Python 3 (python3 on Linux/macOS; python or the py launcher on Windows)
PYTHON=""
for candidate in python3 python py; do
    if "$candidate" --version >/dev/null 2>&1; then
        PYTHON="$candidate"
        break
    fi
done
if [ -z "$PYTHON" ]; then
    echo "Python 3.10 or newer is required but was not found." >&2
    exit 1
fi

if [ ! -d .venv ]; then
    echo "Creating virtual environment..."
    "$PYTHON" -m venv .venv
fi
if [ -f .venv/Scripts/activate ]; then
    source .venv/Scripts/activate      # Windows (Git Bash)
else
    source .venv/bin/activate          # Linux / macOS
fi

echo "Installing dependencies..."
python -m pip install --quiet -r requirements.txt

echo "Running tests against $GANACHE_RPC"
echo
python -m pytest tests -v
