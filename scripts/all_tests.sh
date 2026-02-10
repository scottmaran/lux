#!/usr/bin/env bash
set -euo pipefail

uv run python scripts/all_tests.py "$@"
