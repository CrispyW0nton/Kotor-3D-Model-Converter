"""Diagnostics for the optional Autodesk FBX SDK bridge."""

from __future__ import annotations

from typing import Any

from .fbx_sdk_loader import get_fbx_modules
from .fbx_sdk_paths import (
    FBX_DOWNLOAD_URL,
    get_python_runtime_info,
    normalize_fbx_sdk_settings,
    test_fbx_sdk_configuration,
)
from .fbx_sdk_setup import LICENCE_NOTICE


def build_fbx_diagnostic_report(settings: dict[str, Any] | None = None) -> str:
    """Return a user-facing diagnostic report without requiring Autodesk files."""

    data = normalize_fbx_sdk_settings(settings)
    runtime = get_python_runtime_info(data)
    modules = get_fbx_modules(refresh=True)
    test_result = test_fbx_sdk_configuration(data)

    lines = [
        "Autodesk FBX SDK Diagnostic",
        "",
        "Runtime",
        f"- Python: {runtime['python_version']} ({runtime['architecture']})",
        f"- Executable: {runtime['python_executable']}",
        f"- Platform: {runtime['platform_detail']}",
        f"- Virtual environment: {'yes' if runtime['inside_venv'] else 'no'}",
        f"- Conda environment: {'yes' if runtime['inside_conda'] else 'no'}",
        "",
        "Configured Paths",
    ]
    configured_paths = runtime.get("configured_paths") or []
    if configured_paths:
        lines.extend(f"- {path}" for path in configured_paths)
    else:
        lines.append("- none")

    lines.extend(
        [
            "",
            "Import Status",
            f"- fbx module: {'available' if modules.fbx else 'missing'}",
            f"- FbxCommon.py: {'available' if modules.FbxCommon else 'missing'}",
        ]
    )
    if modules.fbx_error:
        lines.append(f"- fbx import error: {modules.fbx_error}")
    if modules.common_error:
        lines.append(f"- FbxCommon import error: {modules.common_error}")

    lines.extend(
        [
            "",
            "Validation",
            f"- fbx import: {'pass' if test_result.fbx_import_ok else 'fail'}",
            f"- FbxManager.Create(): {'pass' if test_result.manager_create_ok else 'fail'}",
            f"- FbxScene.Create(): {'pass' if test_result.scene_create_ok else 'fail'}",
            f"- FbxCommon import: {'pass' if test_result.fbxcommon_import_ok else 'not required/missing'}",
            f"- Overall: {'pass' if test_result.success else 'fail'}",
        ]
    )
    if test_result.detected_sdk_version:
        lines.append(f"- Detected SDK version: {test_result.detected_sdk_version}")
    if test_result.error_message:
        lines.append(f"- Error: {test_result.error_message}")
    if test_result.recommended_fix:
        lines.append(f"- Recommended fix: {test_result.recommended_fix}")

    lines.extend(
        [
            "",
            "Install Source",
            f"- {FBX_DOWNLOAD_URL}",
            "",
            LICENCE_NOTICE,
        ]
    )
    return "\n".join(lines)
