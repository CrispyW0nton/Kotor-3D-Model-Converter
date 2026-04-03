"""Indoor-kit workflows (headless).

This module loads Holocron Toolset kit folders from disk into the headless data model in
`pykotor.common.indoorkit`.

Qt/Toolset specifics:
- Toolset may show previews; that lives in Toolset code (Qt) and should not be added here.
- This module focuses on deterministic parsing and optional “missing file” reporting.
"""

from __future__ import annotations

import json
import re

from pathlib import Path
from typing import TYPE_CHECKING

from pykotor.common.indoorkit import Kit, KitComponent, KitComponentHook, KitDoor, MDLMDXTuple
from pykotor.common.stream import BinaryReader
from pykotor.resource.formats.bwm import read_bwm
from pykotor.resource.generics.utd import read_utd
from utility.common.geometry import Vector3

if TYPE_CHECKING:
    import os

    MissingFileInfo = tuple[str, Path, str]

_NUM_RE = re.compile(r"(\d+)")


def _get_nums(s: str) -> list[int]:
    """Extract integers from a string in order (Toolset-compatible)."""
    return [int(m.group(1)) for m in _NUM_RE.finditer(s)]


def _load_binary_file(
    file_path: Path,
    *,
    kit_name: str,
    kind: str,
    missing_files: list[MissingFileInfo] | None,
) -> bytes | None:
    if missing_files is None:
        return BinaryReader.load_file(file_path)

    if not file_path.is_file():
        missing_files.append((kit_name, file_path, kind))
        return None

    try:
        return BinaryReader.load_file(file_path)
    except FileNotFoundError:
        missing_files.append((kit_name, file_path, kind))
        return None


def _load_always_folder(
    kit: Kit,
    *,
    always_path: Path,
    kit_name: str,
    missing_files: list[MissingFileInfo] | None,
) -> None:
    if not always_path.is_dir():
        return

    for always_file in always_path.iterdir():
        raw = _load_binary_file(always_file, kit_name=kit_name, kind="always file", missing_files=missing_files)
        if raw is not None:
            kit.always[always_file] = raw


def _load_texture_folder(
    *,
    folder_path: Path,
    target: dict[str, bytes],
    txis: dict[str, bytes],
    kit_name: str,
    missing_files: list[MissingFileInfo] | None,
    kind: str,
    use_upper_txi_name: bool,
) -> None:
    if not folder_path.is_dir():
        return

    for tga_file in (f for f in folder_path.iterdir() if f.suffix.lower() == ".tga"):
        resref = tga_file.stem.upper()
        raw_tga = _load_binary_file(tga_file, kit_name=kit_name, kind=kind, missing_files=missing_files)
        if raw_tga is not None:
            target[resref] = raw_tga

        txi_stem = resref if use_upper_txi_name else tga_file.stem
        txi_path = folder_path / f"{txi_stem}.txi"
        txis[resref] = BinaryReader.load_file(txi_path) if txi_path.is_file() else b""


def _load_skyboxes(
    kit: Kit,
    *,
    skyboxes_path: Path,
    kit_name: str,
    missing_files: list[MissingFileInfo] | None,
) -> None:
    if not skyboxes_path.is_dir():
        return

    for skybox_resref_str in (f.stem.upper() for f in skyboxes_path.iterdir() if f.suffix.lower() == ".mdl"):
        mdl_path = skyboxes_path / f"{skybox_resref_str}.mdl"
        mdx_path = skyboxes_path / f"{skybox_resref_str}.mdx"

        mdl = _load_binary_file(mdl_path, kit_name=kit_name, kind="skybox model", missing_files=missing_files)
        mdx = _load_binary_file(mdx_path, kit_name=kit_name, kind="skybox model", missing_files=missing_files)
        if mdl is None or mdx is None:
            continue

        kit.skyboxes[skybox_resref_str] = MDLMDXTuple(mdl, mdx)


def _load_doorway_padding(
    kit: Kit,
    *,
    doorway_path: Path,
    kit_name: str,
    missing_files: list[MissingFileInfo] | None,
) -> None:
    if not doorway_path.is_dir():
        return

    for padding_id in (f.stem for f in doorway_path.iterdir() if f.suffix.lower() == ".mdl"):
        mdl_path = doorway_path / f"{padding_id}.mdl"
        mdx_path = doorway_path / f"{padding_id}.mdx"
        mdl = _load_binary_file(mdl_path, kit_name=kit_name, kind="doorway padding", missing_files=missing_files)
        mdx = _load_binary_file(mdx_path, kit_name=kit_name, kind="doorway padding", missing_files=missing_files)
        if mdl is None or mdx is None:
            continue

        nums = _get_nums(padding_id)
        if len(nums) < 2:
            continue
        door_id, padding_size = nums[0], nums[1]
        tuple_val = MDLMDXTuple(mdl, mdx)

        if padding_id.lower().startswith("side"):
            kit.side_padding.setdefault(door_id, {})[padding_size] = tuple_val
        if padding_id.lower().startswith("top"):
            kit.top_padding.setdefault(door_id, {})[padding_size] = tuple_val


def _load_doors(
    kit: Kit,
    doors_json: list[dict],
    *,
    base_path: Path,
    kit_name: str,
    missing_files: list[MissingFileInfo] | None,
) -> None:
    for door_json in doors_json:
        utd_k1_path = base_path / f"{door_json['utd_k1']}.utd"
        utd_k2_path = base_path / f"{door_json['utd_k2']}.utd"

        try:
            utd_k1 = read_utd(utd_k1_path)
            utd_k2 = read_utd(utd_k2_path)
        except FileNotFoundError as e:
            if missing_files is not None:
                missing_files.append((kit_name, Path(e.filename or ""), "door utd"))
                continue
            raise

        kit.doors.append(KitDoor(utd_k1, utd_k2, door_json["width"], door_json["height"]))


def _load_components(
    kit: Kit,
    components_json: list[dict],
    *,
    base_path: Path,
    kit_name: str,
    missing_files: list[MissingFileInfo] | None,
) -> None:
    for component_json in components_json:
        try:
            name = component_json["name"]
            component_id = component_json["id"]
        except Exception:
            continue

        wok_path = base_path / f"{component_id}.wok"
        mdl_path = base_path / f"{component_id}.mdl"
        mdx_path = base_path / f"{component_id}.mdx"

        if missing_files is not None:
            if not wok_path.is_file():
                missing_files.append((kit_name, wok_path, "walkmesh"))
                continue
            if not mdl_path.is_file():
                missing_files.append((kit_name, mdl_path, "model"))
                continue
            if not mdx_path.is_file():
                missing_files.append((kit_name, mdx_path, "model extension"))
                continue

        bwm = read_bwm(wok_path)
        mdl = BinaryReader.load_file(mdl_path)
        mdx = BinaryReader.load_file(mdx_path)
        component = KitComponent(kit, name, component_id, bwm, mdl, mdx)

        for hook_json in component_json.get("doorhooks", []):
            try:
                position = Vector3(hook_json["x"], hook_json["y"], hook_json["z"])
                rotation = hook_json["rotation"]
                door = kit.doors[hook_json["door"]]
                edge = int(hook_json["edge"])
            except Exception:
                continue

            component.hooks.append(KitComponentHook(position, rotation, edge, door))

        kit.components.append(component)


def _load_kits_internal(
    path: os.PathLike | str,
    *,
    record_missing: bool,
) -> tuple[list[Kit], list[MissingFileInfo]]:
    kits: list[Kit] = []
    missing_files: list[MissingFileInfo] = []
    missing_ref: list[MissingFileInfo] | None = missing_files if record_missing else None

    kits_path = Path(path).absolute() if record_missing else Path(path)
    if not kits_path.is_dir():
        kits_path.mkdir(parents=True)

    for file in (f for f in kits_path.iterdir() if f.suffix.lower() == ".json"):
        if record_missing:
            try:
                kit_json_raw = json.loads(BinaryReader.load_file(file))
            except Exception:
                continue
            if not isinstance(kit_json_raw, dict) or "name" not in kit_json_raw:
                continue
            kit_json = kit_json_raw
            kit_id = str(kit_json.get("id") or file.stem)
            kit_name = str(kit_json["name"])
        else:
            kit_json = json.loads(BinaryReader.load_file(file))
            kit_id = kit_json.get("id") or file.stem
            kit_name = kit_json["name"]

        kit = Kit(kit_name, kit_id)
        base_path = kits_path / kit_id

        _load_always_folder(kit, always_path=base_path / "always", kit_name=kit_name, missing_files=missing_ref)
        _load_texture_folder(
            folder_path=base_path / "textures",
            target=kit.textures,
            txis=kit.txis,
            kit_name=kit_name,
            missing_files=missing_ref,
            kind="texture",
            use_upper_txi_name=True,
        )
        _load_texture_folder(
            folder_path=base_path / "lightmaps",
            target=kit.lightmaps,
            txis=kit.txis,
            kit_name=kit_name,
            missing_files=missing_ref,
            kind="lightmap",
            use_upper_txi_name=False,
        )
        _load_skyboxes(kit, skyboxes_path=base_path / "skyboxes", kit_name=kit_name, missing_files=missing_ref)
        _load_doorway_padding(kit, doorway_path=base_path / "doorway", kit_name=kit_name, missing_files=missing_ref)
        _load_doors(kit, kit_json.get("doors", []), base_path=base_path, kit_name=kit_name, missing_files=missing_ref)
        _load_components(kit, kit_json.get("components", []), base_path=base_path, kit_name=kit_name, missing_files=missing_ref)

        kits.append(kit)

    return kits, missing_files


def load_kits(path: "os.PathLike | str") -> list[Kit]:
    """Load Holocron indoor kits from disk (headless).

    Expected layout matches Holocron Toolset kits:
    - `<kits>/<kit_id>.json`
    - `<kits>/<kit_id>/...` (folders with resources)
    """
    kits, _missing = _load_kits_internal(path, record_missing=False)
    return kits


def load_kits_with_missing_files(
    path: os.PathLike | str,
) -> tuple[list[Kit], list[tuple[str, Path, str]]]:
    """Load kits and also return a list of missing/invalid referenced files.

    This mirrors the Toolset's historical `load_kits()` behavior (minus Qt preview loading),
    so Toolset UI can report missing resources while keeping all non-Qt logic in PyKotor.
    """
    return _load_kits_internal(path, record_missing=True)
