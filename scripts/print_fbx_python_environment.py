"""Print GhostRigger Autodesk FBX Python SDK environment diagnostics."""

from __future__ import annotations

import importlib
import json
from pathlib import Path
import platform
import struct
import sys

ROOT = Path(__file__).resolve().parents[1]
root_text = str(ROOT)
if root_text not in sys.path:
    sys.path.insert(0, root_text)
try:
    from scripts.mcp.start_kotormcp_stdio import _python_roots

    import_roots = _python_roots(ROOT)
    core_io_root = ROOT / "native" / "GhostRigger.Core.IO" / "Python" / "src"
    if core_io_root.exists():
        import_roots = [core_io_root, *[path for path in import_roots if path != core_io_root]]
except Exception:
    import_roots = [ROOT / "src", ROOT]
for import_root in reversed(import_roots):
    text = str(import_root)
    if import_root.exists() and text not in sys.path:
        sys.path.insert(0, text)

from src.io.fbx.fbx_sdk_paths import apply_configured_sdk_paths, get_python_runtime_info, load_fbx_settings_from_file  # noqa: E402


def _import_status(name: str) -> str:
    try:
        importlib.import_module(name)
        return "OK"
    except Exception as exc:
        return f"{type(exc).__name__}: {exc}"


def main() -> int:
    settings_path = ROOT / "settings.json"
    fbx_settings = load_fbx_settings_from_file(settings_path)
    apply_configured_sdk_paths(fbx_settings)
    info = get_python_runtime_info(fbx_settings)
    print("GhostRigger FBX Python Environment")
    print(f"Python version: {platform.python_version()}")
    print(f"Python executable: {sys.executable}")
    print(f"Architecture: {struct.calcsize('P') * 8}-bit")
    print(f"Platform: {platform.platform()}")
    print("")
    print("Configured GhostRigger FBX SDK paths:")
    print(json.dumps(fbx_settings, indent=2))
    print("")
    print("Runtime info:")
    print(json.dumps(info, indent=2, default=str))
    print("")
    print(f"fbx import status: {_import_status('fbx')}")
    print(f"FbxCommon import status: {_import_status('FbxCommon')}")
    print("")
    print("sys.path:")
    for entry in sys.path:
        print(f"  {entry}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
