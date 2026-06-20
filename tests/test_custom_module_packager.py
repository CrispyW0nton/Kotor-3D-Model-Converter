"""M16/T1605 custom module pack/export tests."""

from __future__ import annotations

import importlib.util as _il_util
import json
import pathlib
import struct
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone


_REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
_SRC_DIR = _REPO_ROOT / "native" / "GhostRigger.Core.Scene" / "Python" / "src"
if str(_SRC_DIR) not in sys.path:
    sys.path.insert(0, str(_SRC_DIR))
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))


def _load_module_direct(name: str, path: pathlib.Path):
    spec = _il_util.spec_from_file_location(name, str(path))
    if spec is None or spec.loader is None:  # pragma: no cover
        raise ImportError(f"cannot create import spec for {path}")
    module = _il_util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


sp = _load_module_direct(
    "ghostrigger_module_save_pipeline_for_packager_test",
    _SRC_DIR / "core" / "modules" / "module_save_pipeline.py",
)
packager = _load_module_direct(
    "ghostrigger_custom_module_packager_under_test",
    _SRC_DIR / "core" / "modules" / "custom_module_packager.py",
)


@dataclass(frozen=True)
class _Record:
    resref: str
    restype: str
    source: str = "module:custom01.mod"


@dataclass
class _Resource:
    record: _Record
    data: bytes = b""
    parsed: object = None


@dataclass
class _Module:
    lyt: object = None
    vis: object = None
    room_woks: dict = field(default_factory=dict)


@dataclass
class _Hydrated:
    module_root: str = "custom01"
    game: str = "K1"
    module: _Module = field(default_factory=_Module)
    resources: dict = field(default_factory=dict)


@dataclass
class _FakeIssue:
    severity: str
    code: str
    message: str


@dataclass
class _FakeReport:
    ok: bool = True
    issues: list[_FakeIssue] = field(default_factory=list)
    code: str = "valid"

    @property
    def blocking_issues(self):
        return [issue for issue in self.issues if issue.severity.lower() == "error"]


class _FakeReferenceSafety:
    report = _FakeReport()

    @classmethod
    def validate_module_references(cls, *_args, **_kwargs):
        return cls.report


class _FakeAreaWOK:
    report = _FakeReport()

    @classmethod
    def validate_area_woks(cls, *_args, **_kwargs):
        return cls.report


class _TextFormat:
    def __init__(self, text):
        self.text = text

    def to_text(self):
        return self.text


class _BinaryFormat:
    def __init__(self, data):
        self.data = data

    def to_bytes(self):
        return self.data


def _resource(resref, restype, data, parsed=None):
    return _Resource(_Record(resref, restype), data=data, parsed=parsed)


def _hydrated():
    lyt = _TextFormat("roomcount 1\n  custom_a 0 0 0\ndonelayout\n")
    vis = _TextFormat("custom_a\n")
    wok = _BinaryFormat(b"WOK-WRITTEN")
    module = _Module(lyt=lyt, vis=vis, room_woks={"custom_a": wok})
    resources = {
        ("custom01", "are"): _resource("custom01", "are", b"ARE-BYTES"),
        ("custom01", "git"): _resource("custom01", "git", b"GIT-BYTES"),
        ("module", "ifo"): _resource("module", "ifo", b"IFO-BYTES"),
    }
    return _Hydrated(module=module, resources=resources)


def _read_erf(path: pathlib.Path):
    data = path.read_bytes()
    sig = data[:4].decode("ascii").strip()
    count = struct.unpack_from("<I", data, 16)[0]
    keylist_off = struct.unpack_from("<I", data, 24)[0]
    reslist_off = struct.unpack_from("<I", data, 28)[0]
    resources = {}
    for index in range(count):
        ko = keylist_off + index * 24
        ro = reslist_off + index * 8
        resref = data[ko:ko + 16].rstrip(b"\x00").decode("ascii")
        restype_id = struct.unpack_from("<H", data, ko + 20)[0]
        offset, size = struct.unpack_from("<II", data, ro)
        resources[(resref, restype_id)] = data[offset:offset + size]
    return sig, resources


def _patch_imports(monkeypatch):
    _FakeReferenceSafety.report = _FakeReport()
    _FakeAreaWOK.report = _FakeReport()
    monkeypatch.setattr(packager, "_import_module_save_pipeline", lambda: sp)
    monkeypatch.setattr(packager, "_import_reference_safety", lambda: _FakeReferenceSafety)
    monkeypatch.setattr(packager, "_import_area_wok_integration", lambda: _FakeAreaWOK)


def test_t1605_exports_install_safe_mod_source_resources_and_manifest(tmp_path, monkeypatch):
    _patch_imports(monkeypatch)
    request = packager.CustomModulePackRequest(
        module_root="custom01",
        game="K1",
        output_dir=str(tmp_path),
    )
    resources = [
        packager.PackagedModuleResource("custom_a", "mdl", b"MDL-BYTES", source="room-model"),
        packager.PackagedModuleResource("custom_a", "mdx", b"MDX-BYTES", source="room-model"),
    ]

    result = packager.package_custom_module(
        _hydrated(),
        request,
        resources=resources,
        now=datetime(2026, 5, 16, 12, 0, tzinfo=timezone.utc),
    )

    assert result.ok is True
    assert result.code == "packaged"
    assert pathlib.Path(result.module_path) == tmp_path / "install" / "Modules" / "custom01.mod"
    assert pathlib.Path(result.module_path).exists()
    sig, archived = _read_erf(pathlib.Path(result.module_path))
    assert sig == "MOD"
    assert archived[("custom01", sp.RESTYPE_IDS["lyt"])] == b"roomcount 1\n  custom_a 0 0 0\ndonelayout\n"
    assert archived[("custom01", sp.RESTYPE_IDS["vis"])] == b"custom_a\n"
    assert archived[("custom_a", sp.RESTYPE_IDS["wok"])] == b"WOK-WRITTEN"
    assert archived[("custom_a", sp.RESTYPE_IDS["mdl"])] == b"MDL-BYTES"
    assert archived[("custom_a", sp.RESTYPE_IDS["mdx"])] == b"MDX-BYTES"
    staged_names = {pathlib.Path(row.path).name for row in result.staged_resources}
    assert {"custom01.lyt", "custom01.vis", "custom_a.wok", "custom_a.mdl", "custom_a.mdx"} <= staged_names
    manifest = json.loads(pathlib.Path(result.manifest_path).read_text(encoding="utf-8"))
    assert manifest["module_root"] == "custom01"
    assert manifest["install"]["module_path"] == result.module_path
    assert manifest["validation"]["blocking_issues"] == []
    assert manifest["source"]["resources"]


def test_t1605_strict_preflight_blocks_missing_game_ready_core_files(tmp_path, monkeypatch):
    _patch_imports(monkeypatch)
    hydrated = _Hydrated(
        module=_Module(
            lyt=_TextFormat("roomcount 1\n  custom_a 0 0 0\ndonelayout\n"),
            vis=_TextFormat("custom_a\n"),
            room_woks={"custom_a": _BinaryFormat(b"WOK")},
        ),
        resources={},
    )
    request = packager.CustomModulePackRequest(module_root="custom01", output_dir=str(tmp_path))

    result = packager.package_custom_module(hydrated, request)

    assert result.ok is False
    assert result.code == "preflight_failed"
    assert any("ARE" in issue for issue in result.blocking_issues)
    assert any("GIT" in issue for issue in result.blocking_issues)
    assert any("IFO" in issue for issue in result.blocking_issues)
    assert not (tmp_path / "install" / "Modules" / "custom01.mod").exists()
    manifest = json.loads(pathlib.Path(result.manifest_path).read_text(encoding="utf-8"))
    assert manifest["validation"]["blocking_issues"] == result.blocking_issues


def test_t1605_validation_errors_block_export_before_writing_mod(tmp_path, monkeypatch):
    _patch_imports(monkeypatch)
    _FakeAreaWOK.report = _FakeReport(
        ok=False,
        issues=[_FakeIssue("error", "ROOM_WOK_MISSING", "Room custom_a has no WOK loaded.")],
        code="invalid",
    )
    request = packager.CustomModulePackRequest(module_root="custom01", output_dir=str(tmp_path))

    result = packager.package_custom_module(_hydrated(), request)

    assert result.ok is False
    assert result.code == "preflight_failed"
    assert "ROOM_WOK_MISSING: Room custom_a has no WOK loaded." in result.blocking_issues
    assert not (tmp_path / "install" / "Modules" / "custom01.mod").exists()


def test_t1605_can_stage_source_from_resource_path(tmp_path, monkeypatch):
    _patch_imports(monkeypatch)
    source_path = tmp_path / "room.mdl"
    source_path.write_bytes(b"MDL-FROM-DISK")
    request = packager.CustomModulePackRequest(
        module_root="custom01",
        output_dir=str(tmp_path / "out"),
        include_wok_check=False,
    )
    resources = [
        packager.PackagedModuleResource("custom_a", "mdl", source_path=str(source_path), source="disk"),
        packager.PackagedModuleResource("custom_a", "mdx", b"MDX", source="disk"),
    ]

    result = packager.package_custom_module(_hydrated(), request, resources=resources)

    assert result.ok is True
    assert (tmp_path / "out" / "source" / "resources" / "custom_a.mdl").read_bytes() == b"MDL-FROM-DISK"
    assert any(row.resref == "custom_a" and row.restype == "mdl" for row in result.staged_resources)
