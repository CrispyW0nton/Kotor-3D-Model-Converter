"""Headless Blender bridge for Sprint 3 reverse animation extraction."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any, Optional

from .fbx_exporter import FBXExportFailure, find_blender_executable


REPO_ROOT = Path(__file__).resolve().parents[3]
BLENDER_EXTRACT_SCRIPT = REPO_ROOT / "scripts" / "blender_extract_ue5_animation.py"


def run_blender_animation_extraction(
    *,
    source_fbx: Path,
    output_json: Path,
    action_name: str = "",
    frame_step: int = 1,
    blender_executable: Optional[Path] = None,
    timeout: int = 300,
) -> dict[str, Any]:
    """Extract UE5 FBX action data to JSON with Blender."""

    if not BLENDER_EXTRACT_SCRIPT.exists():
        return {
            "success": False,
            "errors": [f"Blender extraction script not found: {BLENDER_EXTRACT_SCRIPT}"],
        }

    try:
        blender = find_blender_executable(blender_executable)
    except FBXExportFailure as exc:
        return {"success": False, "errors": [str(exc)]}

    cmd = [
        str(blender),
        "--background",
        "--python",
        str(BLENDER_EXTRACT_SCRIPT),
        "--",
        "--fbx",
        str(source_fbx),
        "--json",
        str(output_json),
        "--frame-step",
        str(max(1, int(frame_step))),
    ]
    if action_name:
        cmd.extend(["--action", action_name])

    output_json.parent.mkdir(parents=True, exist_ok=True)
    log_path = output_json.with_suffix(".blender.log")
    proc = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )
    log_path.write_text(
        f"COMMAND:\n{' '.join(cmd)}\n\nSTDOUT:\n{proc.stdout}\n\nSTDERR:\n{proc.stderr}\n",
        encoding="utf-8",
    )
    if proc.returncode != 0:
        return {
            "success": False,
            "errors": [f"Blender returned {proc.returncode}", proc.stderr[-2000:]],
            "log_path": str(log_path),
        }
    if not output_json.exists():
        return {
            "success": False,
            "errors": ["Blender completed but did not write extraction JSON"],
            "log_path": str(log_path),
        }
    payload = json.loads(output_json.read_text(encoding="utf-8"))
    payload["log_path"] = str(log_path)
    return payload
