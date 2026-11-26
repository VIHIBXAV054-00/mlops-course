#!/usr/bin/env bash
# Regenerates uv.lock and installs the dependencies (needs Python 3.12+).
# You do not need it: uv.lock is committed, so `uv sync --all-groups` is enough.
set -e
uv lock
uv sync --all-groups
echo "Ready. Run: uv run pytest tests/ -v"
