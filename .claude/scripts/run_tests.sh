#!/bin/bash
# Type: Utility
# Purpose: Run pytest with optional coverage. Called from Stop hook or manually.
# Usage: bash .claude/scripts/run_tests.sh [pytest_args]
# Example: bash .claude/scripts/run_tests.sh -k test_parsers -v

set -euo pipefail

# Move to repo root regardless of where the script is called from
REPO_ROOT="$(git rev-parse --show-toplevel 2>/dev/null || echo ".")"
cd "$REPO_ROOT"

if [ ! -d "tests" ]; then
    echo "No tests/ directory found at $REPO_ROOT"
    exit 0
fi

echo "Running pytest from: $REPO_ROOT"
echo "─────────────────────────────────────"

python3 -m pytest tests/ --tb=short -q "$@"
