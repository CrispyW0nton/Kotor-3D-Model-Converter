from __future__ import annotations

import importlib.util
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "compare_grdev01_stock_metadata.py"


def _load_script_module():
    spec = importlib.util.spec_from_file_location("compare_grdev01_stock_metadata_under_test", SCRIPT)
    assert spec is not None
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


class _FakeResource:
    def __init__(self, resref: str, restype: object, data: bytes) -> None:
        self.resref = resref
        self.restype = restype
        self.size = len(data)
        self.data = data


class _FakeArchive:
    def __init__(self, resources: list[_FakeResource]) -> None:
        self._resources = resources

    def __iter__(self):
        return iter(self._resources)

    def get(self, resref: str, restype: object) -> bytes:
        for resource in self._resources:
            if str(resource.resref).lower() == str(resref).lower() and resource.restype == restype:
                return resource.data
        return b""


def _lyt_for(room: str) -> bytes:
    return f"#MAXLAYOUT ASCII\nbeginlayout\n   roomcount 1\n      {room} 0.0 0.0 0.0\n".encode("latin-1")


def _vis_for(room: str) -> bytes:
    return f"{room} 0\n".encode("latin-1")


def test_t2601_room_identity_accepts_matching_stock_room_identity(monkeypatch) -> None:
    module = _load_script_module()
    from pykotor.resource.type import ResourceType

    room = "m02aa_03a"
    archive = _FakeArchive(
        [
            _FakeResource(room, ResourceType.MDL, b"binary M02aa_03a M02aa_03a_lm0"),
            _FakeResource(room, ResourceType.MDX, b"mdx"),
            _FakeResource(room, ResourceType.WOK, b"wok"),
        ]
    )
    monkeypatch.setattr(module, "_are_room_names", lambda _data: [room])

    report = module._room_identity_report(archive, are_data=b"are", lyt_data=_lyt_for(room), vis_data=_vis_for(room))

    assert report["coherent"] is True
    assert report["warnings"] == []
    assert report["blocking_issues"] == []


def test_t2601_room_identity_warns_when_resource_name_and_mdl_internal_name_diverge(monkeypatch) -> None:
    module = _load_script_module()
    from pykotor.resource.type import ResourceType

    room = "grdev01_03a"
    archive = _FakeArchive(
        [
            _FakeResource(room, ResourceType.MDL, b"binary M02aa_03a M02aa_03a_lm0"),
            _FakeResource(room, ResourceType.MDX, b"mdx"),
            _FakeResource(room, ResourceType.WOK, b"wok"),
        ]
    )
    monkeypatch.setattr(module, "_are_room_names", lambda _data: [room])

    report = module._room_identity_report(archive, are_data=b"are", lyt_data=_lyt_for(room), vis_data=_vis_for(room))

    assert report["coherent"] is False
    assert report["blocking_issues"] == []
    assert report["warnings"]
    assert "grdev01_03a.mdl" in report["warnings"][0]
