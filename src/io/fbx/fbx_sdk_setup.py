"""User-facing setup helpers for Autodesk FBX Python SDK."""

from __future__ import annotations

import logging
import webbrowser
from typing import Any

from .fbx_sdk_paths import (
    FBX_DOWNLOAD_URL,
    FbxSdkTestResult,
    apply_configured_sdk_paths,
    get_python_runtime_info,
    normalize_fbx_sdk_settings,
    test_fbx_sdk_configuration,
)

log = logging.getLogger(__name__)

LICENCE_NOTICE = (
    "Autodesk FBX SDK is an external optional dependency. GhostRigger does not bundle "
    "or redistribute Autodesk SDK files. You must download and install it separately "
    "under Autodesk's licence terms."
)


def compatibility_guidance(settings: dict[str, Any] | None = None) -> str:
    info = get_python_runtime_info(settings)
    fbx_state = "Found" if info["fbx_importable"] else "Not found"
    common_state = "Found" if info["fbxcommon_importable"] else "Not found"
    return "\n".join(
        [
            "Current Python:",
            f"- Version: {info['python_version']}",
            f"- Architecture: {info['architecture']}",
            f"- Executable: {info['python_executable']}",
            f"- Platform: {info['platform_detail']}",
            "",
            "FBX SDK Status:",
            f"- fbx module: {fbx_state}",
            f"- FbxCommon.py: {common_state}",
            "",
            "Action:",
            "Download Autodesk FBX Python SDK / Python bindings matching your Python version and platform from Autodesk's official FBX SDK page.",
            "GhostRigger cannot bundle Autodesk SDK files due to external licensing.",
            "",
            "Important:",
            "Autodesk's older documentation references Python 3.1-era bindings. Modern users may need a newer Autodesk FBX SDK release or matching Python binding package.",
            "If Autodesk does not provide bindings for the exact Python version, use a supported Python version or configure a dedicated GhostRigger Python environment.",
            "",
            LICENCE_NOTICE,
        ]
    )


def open_autodesk_fbx_download_page() -> bool:
    ok = bool(webbrowser.open(FBX_DOWNLOAD_URL))
    log.info("Opened Autodesk FBX SDK download page.")
    return ok


def save_successful_configuration(settings: dict[str, Any], result: FbxSdkTestResult) -> dict[str, Any]:
    data = normalize_fbx_sdk_settings(settings)
    info = get_python_runtime_info(data)
    data.update(
        {
            "enabled": bool(result.success),
            "last_verified_python": info["python_version"],
            "last_verified_platform": f"{info['platform']}-{info['architecture']}",
            "last_verified_ok": bool(result.success),
        }
    )
    if result.detected_sdk_version:
        data["detected_sdk_version"] = result.detected_sdk_version
    if result.success:
        apply_configured_sdk_paths(data)
        log.info("FBX SDK detected: %s", result.detected_sdk_version or "unknown version")
    else:
        log.warning("FBX SDK validation failed: %s", result.error_message or result.recommended_fix)
    return data


def validate_and_prepare(settings: dict[str, Any]) -> FbxSdkTestResult:
    data = normalize_fbx_sdk_settings(settings)
    result = test_fbx_sdk_configuration(data)
    if result.success:
        apply_configured_sdk_paths(data)
    return result

