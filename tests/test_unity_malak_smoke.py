import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LOCAL_SRC = ROOT / "src"
if str(LOCAL_SRC) not in sys.path:
    sys.path.insert(0, str(LOCAL_SRC))

from src.core.unity_malak_smoke import (
    DEFAULT_ASSET_PATH,
    choose_preferred_clip,
    metadata_path_for_asset,
    run_malak_main_menu_smoke,
)
from kotormcp.tools import get_all_tools


class _FakeUnityClient:
    def __init__(self, tmp_path, *, include_animator=True, renderer_type="UnityEngine.SkinnedMeshRenderer"):
        self.tmp_path = tmp_path
        self.include_animator = include_animator
        self.renderer_type = renderer_type
        self.calls = []
        self.screenshot_index = 0

    def request(self, method, params=None):
        self.calls.append((method, params or {}))
        if method == "scene.open":
            return {"ok": True, "scene": {"path": params["path"], "isLoaded": True}}
        if method == "asset.refresh":
            return {"ok": True, "refreshed": True}
        if method == "asset.find":
            return {"ok": True, "assets": [{"path": DEFAULT_ASSET_PATH, "type": "UnityEngine.GameObject"}]}
        if method == "screenshot.capture":
            return {"ok": True, "path": self._write_screenshot()}
        if method == "scene.get_hierarchy":
            return {
                "ok": True,
                "roots": [{
                    "name": "_MCP_KotorMainMenu",
                    "instanceId": 1,
                    "children": [{
                        "name": "MalakMenuModel_Animated006J",
                        "instanceId": 2,
                        "children": [{
                            "name": "torso",
                            "instanceId": 3,
                            "children": [],
                        }],
                    }],
                }],
            }
        if method == "gameobject.find":
            return {
                "ok": True,
                "matches": [{
                    "name": "MalakMenuModel_Animated006J",
                    "instanceId": 2,
                    "scenePath": "Assets/MCPGhostTests/MainMenuRecreation/MCP_Kotor_MainMenu_Recreation.unity",
                }],
            }
        if method == "component.get":
            instance_id = params["instanceId"]
            if instance_id == 2:
                components = [{"type": "UnityEngine.Transform"}]
                if self.include_animator:
                    components.append({"type": "UnityEngine.Animator"})
                return {"ok": True, "components": components}
            if instance_id == 3:
                return {"ok": True, "components": [{"type": self.renderer_type}]}
            return {"ok": True, "components": []}
        if method in {"compile.diagnostics_get", "console.diagnostics_get"}:
            return {"ok": True, "diagnostics": []}
        raise AssertionError(f"Unexpected Unity method: {method}")

    def _write_screenshot(self):
        from PIL import Image

        self.screenshot_index += 1
        path = self.tmp_path / f"shot-{self.screenshot_index}.png"
        color = (0, 0, 0) if self.screenshot_index == 1 else (64, 0, 0)
        Image.new("RGB", (4, 4), color).save(path)
        return str(path)


def _write_sidecar(unity_project: Path):
    sidecar = metadata_path_for_asset(unity_project, DEFAULT_ASSET_PATH)
    sidecar.parent.mkdir(parents=True, exist_ok=True)
    sidecar.write_text(json.dumps({
        "animations": ["walk", "pause1", "tlknorm"],
        "counts": {"animations": 3},
    }), encoding="utf-8")
    return sidecar


def test_choose_preferred_clip_uses_menu_priority():
    assert choose_preferred_clip(["walk", "pause2", "pause1"]) == "pause1"
    assert choose_preferred_clip(["custom_idle"]) == "custom_idle"
    assert choose_preferred_clip([]) is None


def test_metadata_path_for_asset_uses_ghostrigger_sidecar_name():
    unity_project = Path("C:/Unity/Kotor-Unity")

    path = metadata_path_for_asset(unity_project, DEFAULT_ASSET_PATH)

    assert path.as_posix().endswith(
        "Assets/KotorImported/MainMenu/Models/Malak/GhostRiggerFresh/"
        "N_DarthMalak_GhostRiggerFresh.ghostrigger.json"
    )


def test_run_malak_main_menu_smoke_writes_report(tmp_path):
    unity_project = tmp_path / "UnityProject"
    _write_sidecar(unity_project)
    client = _FakeUnityClient(tmp_path)
    output = tmp_path / "report.json"

    report = run_malak_main_menu_smoke(
        unity_project=unity_project,
        client=client,
        output_path=output,
        screenshot_delay=0.0,
    )

    assert report["status"] == "ok"
    assert report["ok"] is True
    assert report["selected_clip"] == "pause1"
    assert report["unity_summary"]["malak_instance_count"] == 1
    assert report["unity_summary"]["component_types"]["UnityEngine.Animator"] == 1
    assert report["screenshot_delta"]["visible_delta"] is True
    assert output.exists()
    assert [call[0] for call in client.calls][:3] == ["scene.open", "asset.refresh", "asset.find"]


def test_run_malak_main_menu_smoke_reports_missing_animator(tmp_path):
    unity_project = tmp_path / "UnityProject"
    _write_sidecar(unity_project)

    report = run_malak_main_menu_smoke(
        unity_project=unity_project,
        client=_FakeUnityClient(tmp_path, include_animator=False),
        screenshot_delay=0.0,
    )

    assert report["status"] == "error"
    assert report["ok"] is False
    assert {issue["code"] for issue in report["issues"]} == {"animator_missing"}


def test_mcp_tool_manifest_exposes_malak_smoke_action():
    names = {tool["name"] for tool in get_all_tools()}

    assert "ghostrigger_run_malak_unity_smoke" in names
