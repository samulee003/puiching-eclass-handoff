#!/usr/bin/env bash
# POSIX shell wrapper to run the full puiching-eclass-handoff E2E test suite.
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"

export PYTHONPATH="${PROJECT_ROOT}:${SCRIPT_DIR}:${PYTHONPATH}"

echo "Starting puiching-eclass-handoff test runner..."
python3 "${SCRIPT_DIR}/run_all_tests.py"
