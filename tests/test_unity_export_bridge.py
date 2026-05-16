import asyncio
import json
import shutil
import sys
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
LOCAL_SRC = ROOT / "src"
if str(LOCAL_SRC) not in sys.path:
    sys.path.insert(0, str(LOCAL_SRC))

from src.core.unity_export_bridge import build_output_paths, summarize_model
from kotormcp.tools import get_all_tools, handle_tool
from kotormcp.tools import ghostrigger


class _Node:
    def __init__(self, name, is_mesh=False, vertices=None, faces=None):
        self.name = name
        self.is_mesh = is_mesh
        self.vertices = vertices or []
        self.faces = faces or []


class _Anim:
    def __init__(self, name):
        self.name = name


class _Model:
    name = "n_darthmalak"
    supermodel = "NULL"
    model_type = 4
    animations = [_Anim("pause1"), _Anim("tlknorm")]

    def all_nodes(self):
        return [
            _Node("n_darthmalak"),
            _Node("headhook"),
            _Node("torso", is_mesh=True, vertices=[1, 2, 3], faces=[1]),
        ]


def test_build_output_paths_stays_inside_unity_assets():
    unity_project = Path("C:/Unity/Kotor-Unity")

    asset_path, metadata_path = build_output_paths(
        unity_project,
        "Assets/KotorImported/MainMenu/Models/Malak",
        "n_darthmalak",
        "fbx",
    )

    assert asset_path == unity_project / "Assets/KotorImported/MainMenu/Models/Malak/n_darthmalak.fbx"
    assert metadata_path == unity_project / "Assets/KotorImported/MainMenu/Models/Malak/n_darthmalak.ghostrigger.json"


def test_summarize_model_records_counts_and_unity_asset_path():
    unity_project = Path("C:/Unity/Kotor-Unity")
    asset_path = unity_project / "Assets/KotorImported/Malak/n_darthmalak.fbx"

    metadata = summarize_model(_Model(), "K1", "n_darthmalak", asset_path, unity_project)

    assert metadata["source"]["game"] == "K1"
    assert metadata["source"]["resref"] == "n_darthmalak"
    assert metadata["counts"]["nodes"] == 3
    assert metadata["counts"]["mesh_nodes"] == 1
    assert metadata["counts"]["vertices"] == 3
    assert metadata["counts"]["faces"] == 1
    assert metadata["counts"]["animations"] == 2
    assert metadata["animations"] == ["pause1", "tlknorm"]
    assert metadata["unity"]["asset_path"] == "Assets/KotorImported/Malak/n_darthmalak.fbx"


def test_mcp_tool_manifest_exposes_unity_export_action():
    names = {tool["name"] for tool in get_all_tools()}

    assert "ghostrigger_export_model_for_unity" in names


def test_mcp_unity_export_action_writes_asset_and_metadata(monkeypatch):
    out_root = Path(".pytest_tmp_unity_bridge") / "UnityProject"

    class _Locator:
        def locate(self, resref, game, game_path):
            assert resref == "n_darthmalak"
            assert game == "k1"
            return "installation:n_darthmalak.mdl", b"mdl", b"mdx"

    class _Parser:
        def parse(self, mdl_bytes, mdx_bytes, path_label):
            assert mdl_bytes == b"mdl"
            assert mdx_bytes == b"mdx"
            return _Model()

    def _fake_exporter(model, out_path, export_rigging):
        assert export_rigging is True
        out_path.write_text("fbx", encoding="utf-8")
        return True

    services = SimpleNamespace(locator=_Locator(), parser=_Parser(), analyzer=None, registry=None)
    monkeypatch.setattr(ghostrigger, "_get_services", lambda: services)
    monkeypatch.setattr(ghostrigger, "_export_fbx_for_unity", _fake_exporter)

    try:
        result = asyncio.run(handle_tool(
            "ghostrigger_export_model_for_unity",
            {
                "game": "k1",
                "resref": "n_darthmalak",
                "unity_project": str(out_root),
                "asset_subdir": "Assets/KotorImported/Test",
            },
        ))
        payload = json.loads(result["text"])

        assert payload["status"] == "ok"
        assert payload["unity_asset_path"] == "Assets/KotorImported/Test/n_darthmalak.fbx"
        assert Path(payload["asset"]).exists()
        assert Path(payload["metadata"]).exists()
        sidecar = json.loads(Path(payload["metadata"]).read_text(encoding="utf-8"))
        assert sidecar["source"]["path"] == "installation:n_darthmalak.mdl"
        assert sidecar["counts"]["animations"] == 2
    finally:
        shutil.rmtree(out_root.parent, ignore_errors=True)
