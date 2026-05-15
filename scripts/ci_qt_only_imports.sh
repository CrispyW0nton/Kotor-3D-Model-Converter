#!/usr/bin/env bash
# scripts/ci_qt_only_imports.sh — M3/T305 CI guard entry point.
#
# Runs the Qt-only imports test (tests/test_qt_only_imports.py) which:
#   * AST-scans every src/gui/*.py for tkinter imports (Layer 1).
#   * Asserts the eight Tk modules deleted in M3/T302 stay deleted.
#   * Live-probes Qt module imports under a tkinter ban (Layer 2,
#     auto-skipped when PySide6 / pykotor / moderngl / numpy / PIL are
#     not installed).
#
# Call this script from any CI runner, git pre-push hook, or local
# developer shell. It exits non-zero on the first regression so the
# PR / build is blocked.
#
# Usage:
#   bash scripts/ci_qt_only_imports.sh
#
# Adding to GitHub Actions (when workflows-permission token is
# available — see knowledge_base/reference/ci_qt_only_imports.md for
# the ready-to-commit YAML snippet):
#   - run: bash scripts/ci_qt_only_imports.sh
#
# Roadmap: knowledge_base/roadmap/02_roadmap_2026_05.md M3/T305.

set -euo pipefail

cd "$(dirname "$0")/.."
echo "[ci-qt-only-imports] python: $(python3 --version)"
echo "[ci-qt-only-imports] cwd:    $(pwd)"
python3 -m pip install --quiet --upgrade pip pytest
python3 -m pytest tests/test_qt_only_imports.py -v -ra
