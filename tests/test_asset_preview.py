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
    def __init__(self, name, nodes=None, animations=None):
        self.name = name
        self._nodes = list(nodes or [])
        self.animations = list(animations or [])

    def all_nodes(self):
        return list(self._nodes)


class _Anim:
    def __init__(self, name, length=1.0):
        self.name = name
        self.length = length


class _Node:
    def __init__(self, name, position=(0.0, 0.0, 0.0), rotation=(0.0, 0.0, 0.0, 1.0)):
        self.name = name
        self.position = position
        self.rotation = rotation

    def world_transform(self):
        return self.position, self.rotation


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
        body = _Model(
            Path(kwargs["body_path"]).stem,
            nodes=[
                _Node("rootdummy"),
                _Node("rhand", (1.0, 2.0, 3.0)),
                _Node("lhand", (-1.0, 2.0, 3.0)),
                _Node("LightsaberHook", (0.2, 0.4, 0.6)),
                _Node("DeflectHook", (0.0, 0.0, 1.0)),
            ],
        )
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


def test_t1402_available_attachment_sockets_lists_body_hooks(monkeypatch):
    _install(monkeypatch)
    spec = ap.CharacterPreviewSpec(body_path="body.mdl", head_path="head.mdl")
    result = ap.load_character_preview(spec)

    sockets = ap.available_attachment_sockets(result.scene)

    assert sockets == ["DeflectHook", "lhand", "LightsaberHook", "rhand"]


def test_t1402_attach_item_to_right_hand_records_scene_metadata(monkeypatch):
    _install(monkeypatch)
    result = ap.load_character_preview(ap.CharacterPreviewSpec(body_path="body.mdl", head_path="head.mdl"))
    item = _Model("w_blstrpstl_001", nodes=[_Node("bullethook")])

    attach = ap.attach_item_to_preview(
        result.scene,
        ap.AttachmentSpec(
            item_model=item,
            item_path="C:/kotor/w_blstrpstl_001.mdl",
            item_resref="w_blstrpstl_001",
            socket="right_hand",
            attachment_type="weapon",
        ),
    )

    assert attach.ok is True
    assert attach.socket_name == "rhand"
    assert attach.item_local_offset[0][3] == 1.0
    assert attach.item_local_offset[1][3] == 2.0
    assert attach.item_local_offset[2][3] == 3.0
    assert item.preview_parent_socket == "rhand"
    assert item.preview_attachment_type == "weapon"
    assert result.scene.get_model(md.PartSlot.ACCESSORY) is item
    metadata = result.scene.metadata["asset_preview"]["attachments"][0]
    assert metadata["item_resref"] == "w_blstrpstl_001"
    assert metadata["socket"] == "rhand"


def test_t1402_attach_lightsaber_prefers_lightsaber_hook(monkeypatch):
    _install(monkeypatch)
    result = ap.load_character_preview(ap.CharacterPreviewSpec(body_path="body.mdl", head_path="head.mdl"))
    saber = _Model("w_lghtsbr_001")

    attach = ap.attach_item_to_preview(
        result.scene,
        ap.AttachmentSpec(item_model=saber, item_resref="w_lghtsbr_001", socket="lightsaber"),
    )

    assert attach.ok is True
    assert attach.socket_name == "LightsaberHook"
    assert saber.preview_socket_alias == "lightsaber"


def test_t1402_attach_reports_missing_socket(monkeypatch):
    _install(monkeypatch)
    result = ap.load_character_preview(ap.CharacterPreviewSpec(body_path="body.mdl", head_path="head.mdl"))

    attach = ap.attach_item_to_preview(
        result.scene,
        ap.AttachmentSpec(item_model=_Model("mask"), socket="maskhook"),
    )

    assert attach.ok is False
    assert attach.code == "socket_missing"
    assert "DeflectHook" in attach.warnings[0]


def test_t1402_attach_requires_preview_body(monkeypatch):
    _install(monkeypatch)
    scene = md.CharacterScene(game_version="K1")

    attach = ap.attach_item_to_preview(
        scene,
        ap.AttachmentSpec(item_model=_Model("w_blstrpstl_001"), socket="right_hand"),
    )

    assert attach.ok is False
    assert attach.code == "preview_body_missing"


def test_t1403_animation_workbench_groups_body_and_item_clips(monkeypatch):
    _install(monkeypatch)
    result = ap.load_character_preview(ap.CharacterPreviewSpec(body_path="body.mdl", head_path="head.mdl"))
    body = result.scene.get_model(md.PartSlot.HEADLESS_BODY)
    body.animations = [
        _Anim("pause1", 3.0),
        _Anim("walk", 1.2),
        _Anim("tlknorm", 2.0),
        _Anim("c2a1", 0.9),
    ]
    saber = _Model("w_lghtsbr_001", animations=[_Anim("powered", 1.0), _Anim("off", 1.0)])
    ap.attach_item_to_preview(
        result.scene,
        ap.AttachmentSpec(item_model=saber, item_resref="w_lghtsbr_001", socket="lightsaber"),
    )

    workbench = ap.build_animation_workbench(result.scene)

    assert workbench.ok is True
    assert workbench.selected.name == "pause1"
    assert [clip.name for clip in workbench.groups["idle"]] == ["pause1"]
    assert [clip.name for clip in workbench.groups["locomotion"]] == ["walk"]
    assert [clip.name for clip in workbench.groups["talk"]] == ["tlknorm"]
    assert [clip.name for clip in workbench.groups["combat"]] == ["c2a1"]
    assert [clip.name for clip in workbench.groups["item"]] == ["off", "powered"]
    assert result.scene.metadata["asset_preview"]["animation_workbench"]["groups"]["item"][0]["source"] == "item"


def test_t1403_animation_workbench_shows_inherited_supermodel_source(monkeypatch):
    _install(monkeypatch)
    result = ap.load_character_preview(ap.CharacterPreviewSpec(body_path="body.mdl", head_path="head.mdl"))
    result.scene.motion_assignment = {
        "source": "inherited_supermodel",
        "supermodel": "S_Female02",
    }

    workbench = ap.build_animation_workbench(result.scene)

    inherited = [clip for clip in workbench.clips if clip.inherited]
    assert workbench.ok is True
    assert inherited
    assert {clip.source_model for clip in inherited} == {"S_Female02"}
    assert "walk" in {clip.name for clip in workbench.groups["locomotion"]}
    assert "tlknorm" in {clip.name for clip in workbench.groups["talk"]}
    assert result.scene.metadata["asset_preview"]["animation_workbench"]["groups"]["idle"][0]["inherited"] is True


def test_t1403_play_preview_animation_records_source_and_time(monkeypatch):
    _install(monkeypatch)
    result = ap.load_character_preview(ap.CharacterPreviewSpec(body_path="body.mdl", head_path="head.mdl"))
    body = result.scene.get_model(md.PartSlot.HEADLESS_BODY)
    body.animations = [_Anim("walk", 1.25)]

    state = ap.play_preview_animation(result.scene, "walk", time=2.75)

    assert state.ok is True
    assert state.code == "playing"
    assert state.clip_name == "walk"
    assert state.group == "locomotion"
    assert state.source_model == "body"
    assert state.time == 0.25
    playback = result.scene.metadata["asset_preview"]["playback"]
    assert playback["clip"] == "walk"
    assert playback["source"] == "model"
    assert playback["duration"] == 1.25


def test_t1403_scrub_preview_animation_updates_existing_state(monkeypatch):
    _install(monkeypatch)
    result = ap.load_character_preview(ap.CharacterPreviewSpec(body_path="body.mdl", head_path="head.mdl"))
    body = result.scene.get_model(md.PartSlot.HEADLESS_BODY)
    body.animations = [_Anim("pause1", 3.0)]
    ap.play_preview_animation(result.scene, "pause1")

    state = ap.scrub_preview_animation(result.scene, 4.25)

    assert state.ok is True
    assert state.code == "scrubbed"
    assert state.time == 1.25
    assert result.scene.metadata["asset_preview"]["playback"]["code"] == "scrubbed"
    assert result.scene.metadata["asset_preview"]["playback"]["time"] == 1.25


def test_t1403_play_reports_missing_clip(monkeypatch):
    _install(monkeypatch)
    result = ap.load_character_preview(ap.CharacterPreviewSpec(body_path="body.mdl", head_path="head.mdl"))
    body = result.scene.get_model(md.PartSlot.HEADLESS_BODY)
    body.animations = [_Anim("pause1", 3.0)]

    state = ap.play_preview_animation(result.scene, "run")

    assert state.ok is False
    assert state.code == "clip_missing"


def test_t1404_attachment_validation_clean_lightsaber(monkeypatch):
    _install(monkeypatch)
    result = ap.load_character_preview(ap.CharacterPreviewSpec(body_path="body.mdl", head_path="head.mdl"))
    saber = _Model("w_lghtsbr_001")
    ap.attach_item_to_preview(
        result.scene,
        ap.AttachmentSpec(item_model=saber, item_resref="w_lghtsbr_001", socket="lightsaber"),
    )

    report = ap.validate_attachment_overlay(result.scene)

    assert report.ok is True
    assert report.issues == []
    assert report.overlay == []
    assert "LightsaberHook" in report.available_sockets
    assert result.scene.metadata["asset_preview"]["attachment_validation"]["ok"] is True


def test_t1404_attachment_validation_reports_missing_socket_after_body_change(monkeypatch):
    _install(monkeypatch)
    result = ap.load_character_preview(ap.CharacterPreviewSpec(body_path="body.mdl", head_path="head.mdl"))
    ap.attach_item_to_preview(
        result.scene,
        ap.AttachmentSpec(item_model=_Model("w_blstrpstl_001"), item_resref="w_blstrpstl_001"),
    )
    body = result.scene.get_model(md.PartSlot.HEADLESS_BODY)
    body._nodes = [_Node("rootdummy"), _Node("lhand")]

    report = ap.validate_attachment_overlay(result.scene)

    assert report.ok is False
    assert report.code == "errors"
    assert report.issues[0].code == "ATTACHMENT_SOCKET_MISSING"
    assert report.issues[0].socket == "rhand"
    assert result.scene.metadata["asset_preview"]["attachment_validation"]["overlay"][0]["code"] == "ATTACHMENT_SOCKET_MISSING"


def test_t1404_attachment_validation_reports_wrong_hand(monkeypatch):
    _install(monkeypatch)
    result = ap.load_character_preview(ap.CharacterPreviewSpec(body_path="body.mdl", head_path="head.mdl"))
    ap.attach_item_to_preview(
        result.scene,
        ap.AttachmentSpec(
            item_model=_Model("w_shortswrd_001"),
            item_resref="w_shortswrd_001",
            socket="right_hand",
            side="left",
        ),
    )

    report = ap.validate_attachment_overlay(result.scene)

    assert report.ok is True
    assert [issue.code for issue in report.issues] == ["WRONG_HAND_ATTACHMENT"]
    assert report.overlay[0]["severity"] == "warning"
    assert report.overlay[0]["socket"] == "rhand"


def test_t1404_attachment_validation_reports_game_mismatch(monkeypatch):
    _install(monkeypatch)
    result = ap.load_character_preview(ap.CharacterPreviewSpec(body_path="body.mdl", head_path="head.mdl"))
    item = _Model("w_blstrpstl_001", nodes=[_Node("bullethook")])
    ap.attach_item_to_preview(
        result.scene,
        ap.AttachmentSpec(item_model=item, item_resref="w_blstrpstl_001", socket="right_hand"),
    )
    result.scene.get(md.PartSlot.ACCESSORY).game_version = "K2"

    report = ap.validate_attachment_overlay(result.scene)

    assert report.ok is True
    codes = {issue.code for issue in report.issues}
    assert "ATTACHMENT_GAME_MISMATCH" in codes
    assert result.scene.metadata["asset_preview"]["attachment_validation"]["issues"][0]["severity"] == "warning"


def test_t1404_attachment_validation_reports_stale_transform(monkeypatch):
    _install(monkeypatch)
    result = ap.load_character_preview(ap.CharacterPreviewSpec(body_path="body.mdl", head_path="head.mdl"))
    ap.attach_item_to_preview(
        result.scene,
        ap.AttachmentSpec(item_model=_Model("w_shortswrd_001"), item_resref="w_shortswrd_001"),
    )
    body = result.scene.get_model(md.PartSlot.HEADLESS_BODY)
    for node in body._nodes:
        if node.name == "rhand":
            node.position = (9.0, 9.0, 9.0)

    report = ap.validate_attachment_overlay(result.scene)

    assert report.ok is True
    assert [issue.code for issue in report.issues] == ["ATTACHMENT_TRANSFORM_STALE"]
    assert report.overlay[0]["overlay_anchor"][0][3] == 9.0


def test_t1404_attachment_validation_reports_missing_blaster_bullet_hook(monkeypatch):
    _install(monkeypatch)
    result = ap.load_character_preview(ap.CharacterPreviewSpec(body_path="body.mdl", head_path="head.mdl"))
    ap.attach_item_to_preview(
        result.scene,
        ap.AttachmentSpec(
            item_model=_Model("w_blstrpstl_001"),
            item_resref="w_blstrpstl_001",
            attachment_type="blaster",
        ),
    )

    report = ap.validate_attachment_overlay(result.scene)

    assert report.ok is True
    assert [issue.code for issue in report.issues] == ["BULLET_HOOK_MISSING"]
    assert "bullethook" in report.issues[0].action
