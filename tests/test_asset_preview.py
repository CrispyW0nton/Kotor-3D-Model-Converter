import sys
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
LOCAL_SRC = ROOT / "src"
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
if str(LOCAL_SRC) not in sys.path:
    sys.path.insert(0, str(LOCAL_SRC))

from src.core import asset_preview as ap
from src.core import model_data as md


class _Model:
    def __init__(self, name):
        self.name = name


@dataclass
class _Snap:
    ok: bool = True
    preview_model: object = None
    warnings: list = None
    code: str = "snapped"
    message: str = "snap ok"
    headhook_name: str = "headhook"
    head_local_offset: tuple = ((1, 0, 0, 0), (0, 1, 0, 0), (0, 0, 1, 1.7), (0, 0, 0, 1))


@dataclass
class _Composite:
    ok: bool = True
    snap: object = None
    message: str = "Composite loaded and snapped."
    code: str = "loaded"


class _CompositeWorkflow:
    calls = []
    refresh_calls = []

    @staticmethod
    def load_composite(scene, **kwargs):
        _CompositeWorkflow.calls.append(kwargs)
        body = _Model(Path(kwargs["body_path"]).stem)
        head = _Model(Path(kwargs["head_path"]).stem)
        scene.assign(md.PartSlot.HEADLESS_BODY, body, resref=body.name, source_path=kwargs["body_path"])
        scene.assign(md.PartSlot.HEAD_SHELL, head, resref=head.name, source_path=kwargs["head_path"])
        scene.set_mode(md.CharacterMode.SUPERMODEL, locked=False)
        snap = _Snap(preview_model=_Model("preview"), warnings=["preview note"])
        return _Composite(snap=snap)

    @staticmethod
    def update_snap_after_scene_mutation(scene, **kwargs):
        _CompositeWorkflow.refresh_calls.append(kwargs)
        return _Snap(preview_model=_Model("refreshed"), warnings=[])


def _install(monkeypatch):
    _CompositeWorkflow.calls = []
    _CompositeWorkflow.refresh_calls = []
    monkeypatch.setattr(ap, "_import_model_data", lambda: md)
    monkeypatch.setattr(ap, "_import_composite_workflow", lambda: _CompositeWorkflow)


def test_t1401_character_preview_loads_body_head_with_m7_composite(monkeypatch):
    _install(monkeypatch)
    spec = ap.CharacterPreviewSpec(
        body_path="C:/kotor/pmbam.mdl",
        head_path="C:/kotor/pmhc01.mdl",
        game_version="K1",
    )

    result = ap.load_character_preview(spec)

    assert result.ok is True
    assert result.code == "loaded"
    assert result.scene.mode == md.CharacterMode.SUPERMODEL
    assert result.visible_body_model.name == "pmbam"
    assert result.head_model.name == "pmhc01"
    assert result.preview_model.name == "preview"
    assert _CompositeWorkflow.calls[0]["body_path"] == "C:/kotor/pmbam.mdl"
    assert _CompositeWorkflow.calls[0]["head_path"] == "C:/kotor/pmhc01.mdl"
    assert result.scene.metadata["asset_preview"]["snap"]["code"] == "snapped"


def test_t1401_character_preview_uses_outfit_as_visible_body(monkeypatch):
    _install(monkeypatch)
    spec = ap.CharacterPreviewSpec(
        body_path="C:/kotor/pmbam.mdl",
        head_path="C:/kotor/pmhc01.mdl",
        outfit_path="C:/kotor/pmbjm.mdl",
        outfit_resref="pmbjm",
    )

    result = ap.load_character_preview(spec)

    assert result.ok is True
    assert _CompositeWorkflow.calls[0]["body_path"] == "C:/kotor/pmbjm.mdl"
    assert result.scene.get_model(md.PartSlot.BODY_VARIANT) is result.visible_body_model
    metadata = result.scene.metadata["asset_preview"]
    assert metadata["active_body_path"] == "C:/kotor/pmbjm.mdl"
    assert metadata["outfit_resref"] == "pmbjm"


def test_t1401_character_preview_reports_missing_required_parts(monkeypatch):
    _install(monkeypatch)

    no_body = ap.load_character_preview(ap.CharacterPreviewSpec(body_path="", head_path="head.mdl"))
    no_head = ap.load_character_preview(ap.CharacterPreviewSpec(body_path="body.mdl", head_path=""))

    assert no_body.ok is False
    assert no_body.code == "body_required"
    assert no_head.ok is False
    assert no_head.code == "head_required"
    assert _CompositeWorkflow.calls == []


def test_t1401_refresh_character_preview_recomputes_snap(monkeypatch):
    _install(monkeypatch)
    scene = md.CharacterScene(game_version="K1")
    scene.assign(md.PartSlot.HEADLESS_BODY, _Model("pmbam"), resref="pmbam")
    scene.assign(md.PartSlot.HEAD_SHELL, _Model("pmhc01"), resref="pmhc01")
    spec = ap.CharacterPreviewSpec(body_path="body.mdl", head_path="head.mdl")

    result = ap.refresh_character_preview(scene, spec, build_preview=False)

    assert result.ok is True
    assert result.preview_model.name == "refreshed"
    assert _CompositeWorkflow.refresh_calls == [{"build_preview": False}]
    assert scene.metadata["asset_preview"]["code"] == "snapped"
