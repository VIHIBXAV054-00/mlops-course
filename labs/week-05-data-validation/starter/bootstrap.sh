#!/usr/bin/env bash
# Run this once after cloning to generate uv.lock (requires Python 3.12+)
# After the initial run the lock file is committed and students just run
# "uv sync --all-groups" without needing this script.
set -e
uv lock
uv sync --all-groups
echo "Ready. Run: uv run pytest tests/ -v"
