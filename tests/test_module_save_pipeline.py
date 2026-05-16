"""M15/T1504 Module Editor save/package pipeline tests."""

from __future__ import annotations

import importlib.util as _il_util
import json
import pathlib
import struct
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone


_REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
_SRC_DIR = _REPO_ROOT / "src"
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
    "ghostrigger_module_save_pipeline_under_test",
    _SRC_DIR / "core" / "module_save_pipeline.py",
)


@dataclass(frozen=True)
class _Record:
    resref: str
    restype: str
    source: str = "module:tar_m02aa.rim"


@dataclass
class _Resource:
    record: _Record
    data: bytes = b""
    parsed: object = None


@dataclass
class _Module:
    name: str = "tar_m02aa"
    game: str = "K1"
    lyt: object = None
    vis: object = None
    wok: object = None
    room_woks: dict = field(default_factory=dict)


@dataclass
class _Hydrated:
    module_root: str = "tar_m02aa"
    game: str = "K1"
    module: _Module = field(default_factory=_Module)
    resources: dict = field(default_factory=dict)


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


def _resource(resref, restype, data, parsed=None, source="module:tar_m02aa.rim"):
    return _Resource(_Record(resref, restype, source), data=data, parsed=parsed)


def _hydrated():
    lyt = _TextFormat("roomcount 1\n  m02aa_01a 0 0 0\ndonelayout\n")
    vis = _TextFormat("m02aa_01a\n  m02aa_01b\n")
    wok = _BinaryFormat(b"BWM-WRITTEN")
    module = _Module(lyt=lyt, vis=vis, wok=wok, room_woks={"m02aa_01a": wok})
    resources = {
        ("m02aa", "are"): _resource("m02aa", "are", b"ARE-ORIGINAL"),
        ("m02aa", "git"): _resource("m02aa", "git", b"GIT-ORIGINAL"),
        ("module", "ifo"): _resource("module", "ifo", b"IFO-ORIGINAL"),
        ("tar_m02aa", "lyt"): _resource("tar_m02aa", "lyt", b"LYT-OLD", parsed=lyt),
        ("tar_m02aa", "vis"): _resource("tar_m02aa", "vis", b"VIS-OLD", parsed=vis),
        ("m02aa_01a", "wok"): _resource("m02aa_01a", "wok", b"WOK-OLD", parsed=wok),
        (
            "g_sithtroop002",
            "utc",
        ): _resource("g_sithtroop002", "utc", b"UTC-ORIGINAL", source="module:tar_m02aa_s.rim"),
        (
            "tar02_larrim",
            "dlg",
        ): _resource("tar02_larrim", "dlg", b"DLG-ORIGINAL", source="module:tar_m02aa_s.rim"),
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


def test_t1504_k1_save_writes_split_rims_manifest_and_backup(tmp_path):
    hydrated = _hydrated()
    old_rim = tmp_path / "tar_m02aa.rim"
    old_rim.write_bytes(b"old archive")
    request = sp.ModuleSaveRequest(
        module_root="tar_m02aa",
        game="K1",
        output_dir=str(tmp_path),
        archive_mode="auto",
    )

    result = sp.save_module_package(
        hydrated,
        request,
        now=datetime(2026, 5, 16, 12, 0, tzinfo=timezone.utc),
    )

    assert result.ok is True
    assert result.code == "saved"
    assert (tmp_path / "tar_m02aa.rim").exists()
    assert (tmp_path / "tar_m02aa_s.rim").exists()
    assert (tmp_path / "tar_m02aa.rim.bak").read_bytes() == b"old archive"
    base_sig, base_resources = _read_erf(tmp_path / "tar_m02aa.rim")
    static_sig, static_resources = _read_erf(tmp_path / "tar_m02aa_s.rim")
    assert base_sig == "RIM"
    assert static_sig == "RIM"
    assert base_resources[("tar_m02aa", sp.RESTYPE_IDS["lyt"])] == hydrated.module.lyt.to_text().encode("latin-1")
    assert base_resources[("tar_m02aa", sp.RESTYPE_IDS["vis"])] == hydrated.module.vis.to_text().encode("latin-1")
    assert base_resources[("m02aa_01a", sp.RESTYPE_IDS["wok"])] == b"BWM-WRITTEN"
    assert static_resources[("g_sithtroop002", sp.RESTYPE_IDS["utc"])] == b"UTC-ORIGINAL"
    manifest = json.loads(pathlib.Path(result.manifest_path).read_text(encoding="utf-8"))
    assert manifest["module_root"] == "tar_m02aa"
    assert manifest["game"] == "K1"
    assert manifest["generated_at"] == "2026-05-16T12:00:00Z"
    assert len(manifest["archives"]) == 2
    changed = {(row["resref"], row["restype"]) for row in manifest["resources"] if row["changed"]}
    assert changed >= {("tar_m02aa", "lyt"), ("tar_m02aa", "vis"), ("m02aa_01a", "wok")}


def test_t1504_k2_auto_save_writes_single_mod_archive(tmp_path):
    hydrated = _hydrated()
    request = sp.ModuleSaveRequest(
        module_root="003ebo",
        game="K2",
        output_dir=str(tmp_path),
    )

    result = sp.save_module_package(hydrated, request)

    assert result.ok is True
    assert len(result.archives) == 1
    assert pathlib.Path(result.archives[0].path).name == "003ebo.mod"
    sig, resources = _read_erf(tmp_path / "003ebo.mod")
    assert sig == "MOD"
    assert ("g_sithtroop002", sp.RESTYPE_IDS["utc"]) in resources
    assert ("m02aa_01a", sp.RESTYPE_IDS["wok"]) in resources


def test_t1504_dirty_gff_without_writer_is_blocking_and_preserves_binary(tmp_path):
    hydrated = _hydrated()
    request = sp.ModuleSaveRequest(
        module_root="tar_m02aa",
        game="K1",
        output_dir=str(tmp_path),
        dirty_resources=(("m02aa", "git"),),
    )

    result = sp.save_module_package(hydrated, request)

    assert result.ok is False
    assert result.code == "saved_with_blockers"
    assert "m02aa.git is marked dirty" in result.blocking_issues[0]
    sig, resources = _read_erf(tmp_path / "tar_m02aa.rim")
    assert sig == "RIM"
    assert resources[("m02aa", sp.RESTYPE_IDS["git"])] == b"GIT-ORIGINAL"
    manifest = json.loads(pathlib.Path(result.manifest_path).read_text(encoding="utf-8"))
    assert manifest["blocking_issues"] == result.blocking_issues


def test_t1504_replacement_bytes_make_dirty_gff_game_ready(tmp_path):
    hydrated = _hydrated()
    request = sp.ModuleSaveRequest(
        module_root="tar_m02aa",
        game="K1",
        output_dir=str(tmp_path),
        dirty_resources=(("m02aa", "git"),),
    )
    replacement = sp.ModuleReplacementResource("m02aa", "git", b"GIT-REWRITTEN", source="test-writer")

    result = sp.save_module_package(hydrated, request, replacements=[replacement])

    assert result.ok is True
    assert result.blocking_issues == []
    _, resources = _read_erf(tmp_path / "tar_m02aa.rim")
    assert resources[("m02aa", sp.RESTYPE_IDS["git"])] == b"GIT-REWRITTEN"
    row = [
        item
        for item in result.manifest.resources
        if item["resref"] == "m02aa" and item["restype"] == "git"
    ][0]
    assert row["changed"] is True
    assert row["serializer"] == "replacement_bytes"


def test_t1504_collect_skips_empty_resources_with_warning(tmp_path):
    hydrated = _Hydrated(
        resources={
            ("empty", "ncs"): _resource("empty", "ncs", b""),
        }
    )
    request = sp.ModuleSaveRequest(module_root="empty_mod", output_dir=str(tmp_path))

    result = sp.save_module_package(hydrated, request)

    assert result.ok is False
    assert result.code == "no_resources"
    assert "empty.ncs has no bytes" in result.warnings[0]
