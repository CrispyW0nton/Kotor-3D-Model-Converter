"""Regression tests for room-model WOK co-loading."""

from __future__ import annotations

import time
from types import SimpleNamespace


def test_resource_manager_uses_kotor_wok_restype():
    from src.core.assets import resource_manager as rm

    assert rm.RES_WOK == 2016
    assert rm.EXT_TO_TYPE["wok"] == 2016


def test_wok_data_rejects_non_bwm_bytes_quickly():
    from src.core.modules.module_format import WOKData

    data = b"PTH V3.28" + (b"\x00" * 4096)
    started = time.perf_counter()
    wok = WOKData.from_bytes(data)

    assert (time.perf_counter() - started) < 0.1
    assert wok.verts == []
    assert wok.faces == []


def test_resource_room_coload_uses_exact_wok_resref_before_short_area_name():
    from src.core.assets.resource_manager import RES_WOK
    from src.gui.windows.qt_main_window import QtGhostRiggerMainWindow

    calls: list[tuple[str, int, str]] = []
    loaded: list[str] = []

    class _Viewport:
        def clear_walkmesh(self):
            loaded.append("clear")

    class _Manager:
        def get(self, name: str, restype: int, game: str):
            calls.append((name, restype, game))
            assert restype == RES_WOK
            return b"BWM V1.0" if name == "m02ae_01a" else None

    window = SimpleNamespace(
        viewport=_Viewport(),
        _current_model=SimpleNamespace(name="M02ae_01a", model_type=0),
        _model_path="K1:m02ae_01a",
        _current_game="K1",
        _resource_manager=_Manager(),
        _derive_wok_resrefs=QtGhostRiggerMainWindow._derive_wok_resrefs,
        _get_resource_manager=lambda: None,
        _infer_game_from_model=lambda _model: "K1",
        _load_walkmesh_source=lambda _source, label: loaded.append(label) or True,
    )

    QtGhostRiggerMainWindow._do_coload_walkmesh(window, None)

    assert calls == [("m02ae_01a", RES_WOK, "K1")]
    assert loaded == ["clear", "K1:m02ae_01a.wok"]


def test_area_models_do_not_populate_animation_retarget_target():
    from src.gui.windows.qt_main_window import QtGhostRiggerMainWindow

    assert QtGhostRiggerMainWindow._supports_animation_retarget_target(
        SimpleNamespace(model_type=0, classification="effect")
    ) is False
    assert QtGhostRiggerMainWindow._supports_animation_retarget_target(
        SimpleNamespace(model_type=4, classification="character")
    ) is True
