"""Regenerate the embedded Python payload for GhostRigger.Core.Graphics."""

from __future__ import annotations

import sys
from pathlib import Path

PROJECT = "GhostRigger.Core.Graphics"
ROOT = Path(__file__).resolve().parents[1]
repo_root = ROOT.parent
sys.path.insert(0, str(repo_root))

from scripts.native_python_payload_generator import generate_project


if __name__ == "__main__":
    generate_project(PROJECT)
