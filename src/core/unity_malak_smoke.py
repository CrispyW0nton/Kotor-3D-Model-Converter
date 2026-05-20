"""Unity MCP smoke test for the GhostRigger Malak main-menu handoff."""

from __future__ import annotations

import json
import re
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib import error, request


DEFAULT_SCENE_PATH = "Assets/MCPGhostTests/MainMenuRecreation/MCP_Kotor_MainMenu_Recreation.unity"
DEFAULT_ASSET_PATH = (
    "Assets/KotorImported/MainMenu/Models/Malak/GhostRiggerFresh/"
    "N_DarthMalak_GhostRiggerFresh.fbx"
)
DEFAULT_INSTANCE_NAME = "MalakMenuModel_Animated006J"
PREFERRED_MALAK_CLIPS = ("pause1", "pause2", "tlknorm", "listen", "walk", "run")
_CONTROL_CHARS = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")


@dataclass(frozen=True)
class UnityBridgeClient:
    """Small JSON-RPC client for the Unity MCP Ghost editor bridge."""

    host: str = "127.0.0.1"
    port: int = 6400
    timeout: float = 30.0

    @property
    def endpoint(self) -> str:
        return f"http://{self.host}:{self.port}/unity-mcp-ghost/"

    def request(self, method: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
        payload = {
            "jsonrpc": "2.0",
            "id": f"ghostrigger-{uuid.uuid4()}",
            "method": method,
            "params": params or {},
        }
        body = json.dumps(payload).encode("utf-8")
        req = request.Request(
            self.endpoint,
            data=body,
            headers={"content-type": "application/json"},
            method="POST",
        )
        try:
            with request.urlopen(req, timeout=self.timeout) as response:
                raw = response.read().decode("utf-8")
                try:
                    rpc = json.loads(raw)
                except json.JSONDecodeError:
                    rpc = json.loads(_CONTROL_CHARS.sub("", raw))
        except error.URLError as exc:  # pragma: no cover - network failure path
            raise RuntimeError(f"Unity MCP bridge request failed for {method}: {exc}") from exc

        if rpc.get("error"):
            message = rpc["error"].get("message", rpc["error"])
            raise RuntimeError(f"Unity MCP bridge returned an error for {method}: {message}")
        result = rpc.get("result")
        return result if isinstance(result, dict) else {"result": result}


def metadata_path_for_asset(unity_project: Path, asset_path: str) -> Path:
    """Return the GhostRigger sidecar path for a Unity asset path."""
    normalized = asset_path.replace("\\", "/")
    if normalized.lower().endswith(".fbx"):
        normalized = normalized[:-4] + ".ghostrigger.json"
    return unity_project / normalized


def choose_preferred_clip(animations: list[Any], preferred: tuple[str, ...] = PREFERRED_MALAK_CLIPS) -> str | None:
    """Choose the clip the main-menu bootstrap should prefer."""
    names = [str(item.get("name", item) if isinstance(item, dict) else item).lstrip("|") for item in animations]
    by_lower = {name.lower(): name for name in names if name}
    for candidate in preferred:
        if candidate.lower() in by_lower:
            return by_lower[candidate.lower()]
    return names[0] if names else None


def _flatten_hierarchy(nodes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    flat: list[dict[str, Any]] = []
    stack = list(reversed(nodes))
    while stack:
        node = stack.pop()
        flat.append(node)
        children = node.get("children") or []
        if isinstance(children, list):
            stack.extend(reversed([child for child in children if isinstance(child, dict)]))
    return flat


def _subtree_from_name(nodes: list[dict[str, Any]], name: str) -> list[dict[str, Any]]:
    for node in _flatten_hierarchy(nodes):
        if str(node.get("name", "")) == name:
            return _flatten_hierarchy([node])
    return []


def _component_types(components_payload: dict[str, Any]) -> list[str]:
    components = components_payload.get("components") or []
    if not isinstance(components, list):
        return []
    return [str(component.get("type", "")) for component in components if isinstance(component, dict)]


def collect_malak_unity_summary(
    client: Any,
    *,
    scene_path: str,
    asset_path: str,
    instance_name: str,
    expected_clips: list[str],
) -> dict[str, Any]:
    """Collect Unity-side facts for the visible Malak menu instance."""
    hierarchy = client.request("scene.get_hierarchy", {"includeInactive": True, "maxDepth": 16})
    nodes = hierarchy.get("roots") or []
    subtree = _subtree_from_name(nodes if isinstance(nodes, list) else [], instance_name)

    renderers: list[dict[str, Any]] = []
    component_types: dict[str, int] = {}
    for node in subtree:
        instance_id = node.get("instanceId")
        if not isinstance(instance_id, int):
            continue
        components = client.request("component.get", {"instanceId": instance_id})
        for ctype in _component_types(components):
            component_types[ctype] = component_types.get(ctype, 0) + 1
            if ctype.endswith("SkinnedMeshRenderer"):
                renderers.append({"type": "SkinnedMeshRenderer", "materialCount": 1})
            elif ctype.endswith("MeshRenderer"):
                renderers.append({"type": "MeshRenderer", "materialCount": 1})

    direct_matches = client.request(
        "gameobject.find",
        {"name": instance_name, "includeInactive": True},
    ).get("matches") or []
    scene_matches = [
        match for match in direct_matches
        if isinstance(match, dict) and match.get("scenePath") == scene_path
    ]

    return {
        "asset_path": asset_path,
        "clips": [{"name": clip} for clip in expected_clips],
        "renderers": renderers,
        "component_types": component_types,
        "malak_instance_count": len(scene_matches),
        "malak_node_count": len(subtree),
    }


def _wait_for_file(path: str, timeout: float = 5.0) -> bool:
    if not path:
        return False
    target = Path(path)
    started = time.monotonic()
    while time.monotonic() - started < timeout:
        if target.exists():
            return True
        time.sleep(0.1)
    return target.exists()


def compare_screenshots(before_path: str, after_path: str) -> dict[str, Any]:
    """Compare screenshots and report visible movement when Pillow is available."""
    if not _wait_for_file(before_path, timeout=30.0) or not _wait_for_file(after_path, timeout=30.0):
        return {
            "checked": False,
            "before": before_path,
            "after": after_path,
            "reason": "screenshot_missing",
        }
    try:
        from PIL import Image, ImageChops, ImageStat  # noqa: PLC0415
    except Exception as exc:  # pragma: no cover - optional dependency path
        return {
            "checked": False,
            "before": before_path,
            "after": after_path,
            "reason": f"pillow_unavailable: {exc}",
        }

    before = Image.open(before_path).convert("RGB")
    after = Image.open(after_path).convert("RGB")
    if before.size != after.size:
        return {
            "checked": False,
            "before": before_path,
            "after": after_path,
            "reason": "screenshot_size_mismatch",
        }

    diff = ImageChops.difference(before, after)
    stat = ImageStat.Stat(diff)
    mean_delta = sum(stat.mean) / len(stat.mean)
    extrema = diff.getextrema()
    changed_channels = sum(1 for channel in extrema for value in channel if value)
    return {
        "checked": True,
        "before": before_path,
        "after": after_path,
        "mean_delta": mean_delta,
        "changed_channels": changed_channels,
        "visible_delta": mean_delta > 0.25,
    }


def run_malak_main_menu_smoke(
    *,
    unity_project: Path,
    client: Any | None = None,
    host: str = "127.0.0.1",
    port: int = 6400,
    scene_path: str = DEFAULT_SCENE_PATH,
    asset_path: str = DEFAULT_ASSET_PATH,
    instance_name: str = DEFAULT_INSTANCE_NAME,
    output_path: Path | None = None,
    screenshot_delay: float = 1.0,
) -> dict[str, Any]:
    """Run the Malak main-menu smoke and optionally write a JSON report."""
    rpc = client or UnityBridgeClient(host=host, port=port)
    asset_name = Path(asset_path).stem
    sidecar_path = metadata_path_for_asset(unity_project, asset_path)
    sidecar = json.loads(sidecar_path.read_text(encoding="utf-8")) if sidecar_path.exists() else {}
    expected_clips = [str(name) for name in sidecar.get("animations", []) if name]
    selected_clip = choose_preferred_clip(expected_clips)

    steps: list[dict[str, Any]] = []
    steps.append({"step": "scene.open", "result": rpc.request("scene.open", {"path": scene_path, "mode": "single"})})
    steps.append({"step": "asset.refresh", "result": rpc.request("asset.refresh", {})})
    assets = rpc.request("asset.find", {"query": asset_name, "limit": 20})
    steps.append({"step": "asset.find", "result": assets})

    before = rpc.request("screenshot.capture", {"superSize": 1})
    time.sleep(max(0.0, screenshot_delay))
    after = rpc.request("screenshot.capture", {"superSize": 1})
    screenshot_delta = compare_screenshots(str(before.get("path", "")), str(after.get("path", "")))

    unity_summary = collect_malak_unity_summary(
        rpc,
        scene_path=scene_path,
        asset_path=asset_path,
        instance_name=instance_name,
        expected_clips=[selected_clip] if selected_clip else [],
    )
    components = unity_summary.get("component_types", {})
    compile_diags = rpc.request("compile.diagnostics_get", {"severity": "error", "limit": 50})
    console_diags = rpc.request("console.diagnostics_get", {"severity": "error", "limit": 50})

    asset_paths = [
        str(asset.get("path", ""))
        for asset in assets.get("assets", [])
        if isinstance(asset, dict)
    ]
    issues: list[dict[str, str]] = []
    if asset_path not in asset_paths:
        issues.append({"code": "asset_not_found", "message": f"Unity could not find {asset_path}."})
    if not selected_clip:
        issues.append({"code": "no_preferred_clip", "message": "GhostRigger sidecar has no preferred Malak idle/talk clip."})
    if unity_summary.get("malak_instance_count", 0) < 1:
        issues.append({"code": "menu_instance_missing", "message": f"{instance_name} is not present in the menu scene."})
    if components.get("UnityEngine.Animator", 0) < 1:
        issues.append({"code": "animator_missing", "message": "Menu Malak instance has no Animator component."})
    if compile_diags.get("diagnostics"):
        issues.append({"code": "compile_errors", "message": "Unity compile diagnostics contain errors."})
    if console_diags.get("diagnostics"):
        issues.append({"code": "console_errors", "message": "Unity console diagnostics contain errors."})

    warnings: list[dict[str, str]] = []
    if screenshot_delta.get("checked") and not screenshot_delta.get("visible_delta"):
        warnings.append({
            "code": "no_visible_delta",
            "message": "Screenshots did not show visible movement; this may require a Unity play/sample command.",
        })
    elif not screenshot_delta.get("checked"):
        warnings.append({
            "code": "screenshot_delta_unchecked",
            "message": str(screenshot_delta.get("reason", "Screenshot delta could not be checked.")),
        })
    renderer_types = {str(renderer.get("type", "")) for renderer in unity_summary.get("renderers", [])}
    if renderer_types and "SkinnedMeshRenderer" not in renderer_types:
        warnings.append({
            "code": "missing_skinned_renderer",
            "message": "Menu Malak imported as MeshRenderer pieces; Unity skin deformation is not proven yet.",
        })

    report = {
        "schema_version": 1,
        "tool": "ghostrigger.malak_main_menu_smoke",
        "status": "error" if issues else ("warning" if warnings else "ok"),
        "ok": not issues,
        "unity_project": str(unity_project),
        "scene_path": scene_path,
        "asset_path": asset_path,
        "sidecar_path": str(sidecar_path),
        "selected_clip": selected_clip,
        "steps": steps,
        "unity_summary": unity_summary,
        "screenshots": {
            "before": before,
            "after": after,
        },
        "screenshot_delta": screenshot_delta,
        "compile_diagnostics": compile_diags,
        "console_diagnostics": console_diags,
        "warnings": warnings,
        "issues": issues,
    }
    if output_path is not None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    return report
