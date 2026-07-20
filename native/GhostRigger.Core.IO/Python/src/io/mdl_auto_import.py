"""Automatic KOTOR MDL file inspection and import.

This module owns the file-level decision that used to live in the Qt worker:
binary versus ASCII, sibling MDX pairing, K1/K2 detection, and model-class
routing.  It deliberately has no Qt dependency so every Ghost Studio surface
can use the same import behavior.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, replace
from pathlib import Path
import re
import struct
from typing import Callable

from pykotor.resource.formats.mdl.mdl_auto import detect_mdl
from pykotor.resource.type import ResourceType

from src.core.game.kotor_loader import load_model_from_bytes
from src.core.geometry.model_data import GameVersion
from src.core.mdl.mdl_parser import MDLAsciiParser


_MODEL_TYPES = {
    0: "effect",
    1: "effects",
    2: "tile",
    4: "character",
    8: "door",
    16: "lightsaber",
    32: "placeable",
    64: "flyer",
}
_MODEL_TYPE_CODES = {name: code for code, name in _MODEL_TYPES.items()}
_MODEL_TYPE_CODES.update({"other": 0, "misc": 2, "item": 32, "rare_char": 64})
_MODEL_WORKFLOWS = {
    "effect": "effect_model",
    "effects": "effect_model",
    "tile": "area_model",
    "character": "character_model",
    "door": "door_model",
    "lightsaber": "lightsaber_model",
    "placeable": "placeable_model",
    "flyer": "character_model",
}
_K1_FUNCTION_POINTERS = {4273776, 4273392, 4254992}
_K2_FUNCTION_POINTERS = {4285200, 4284816, 4285872}


@dataclass(frozen=True)
class MdlImportDecision:
    """Evidence-backed routing selected for one external MDL file."""

    source_path: str
    source_format: str
    import_method: str
    game: str
    game_confidence: str
    game_evidence: str
    model_type: str
    model_type_code: int
    model_workflow: str
    mdx_path: str = ""
    platform: str = "PC"

    def to_dict(self) -> dict[str, object]:
        return asdict(self)

    @property
    def summary(self) -> str:
        pairing = " + sibling MDX" if self.mdx_path else ""
        return (
            f"{self.game} {self.model_type} via {self.import_method}{pairing} "
            f"({self.game_confidence}: {self.game_evidence})"
        )


def inspect_mdl_import(
    mdl_path: str | Path,
    *,
    mdx_path: str | Path = "",
    game_hint: str = "",
    fallback_game: str = "K1",
    k1_root: str | Path = "",
    k2_root: str | Path = "",
) -> MdlImportDecision:
    """Inspect an MDL without parsing its geometry and return its import route."""

    path = _validated_mdl_path(mdl_path)
    raw = path.read_bytes()
    return _decision_for_bytes(
        path,
        raw,
        mdx_path=mdx_path,
        game_hint=game_hint,
        fallback_game=fallback_game,
        k1_root=k1_root,
        k2_root=k2_root,
    )


def load_mdl_auto(
    mdl_path: str | Path,
    *,
    mdx_path: str | Path = "",
    game_hint: str = "",
    fallback_game: str = "K1",
    k1_root: str | Path = "",
    k2_root: str | Path = "",
    progress_callback: Callable[[str, int, int], None] | None = None,
):
    """Load a binary or ASCII KOTOR MDL using the automatically selected route.

    The returned model carries ``_gr_import_decision`` provenance for UI,
    project, and validation consumers.
    """

    path = _validated_mdl_path(mdl_path)
    _report(progress_callback, "Reading model into RAM", 1, 5)
    raw = path.read_bytes()
    decision = _decision_for_bytes(
        path,
        raw,
        mdx_path=mdx_path,
        game_hint=game_hint,
        fallback_game=fallback_game,
        k1_root=k1_root,
        k2_root=k2_root,
    )

    game_version = GameVersion.K2 if decision.game == "K2" else GameVersion.K1
    if decision.source_format == "ascii":
        _report(progress_callback, "Parsing ASCII MDL", 2, 5)
        model = MDLAsciiParser().parse(raw.decode("utf-8", errors="replace").splitlines())
        if model is not None:
            model.mdl_path = str(path)
            model.mdx_path = ""
    else:
        _report(progress_callback, "Reading paired MDX data", 2, 5)
        mdx = Path(decision.mdx_path).read_bytes() if decision.mdx_path else b""
        _report(progress_callback, f"Parsing {decision.game} binary MDL/MDX", 3, 5)
        model = load_model_from_bytes(raw, mdx, game_version=game_version)
        if model is not None:
            model.mdl_path = str(path)
            model.mdx_path = decision.mdx_path

    if model is None:
        raise RuntimeError(f"Could not parse {path.name} using {decision.import_method}")

    model.game_version = game_version
    classification = str(getattr(model, "classification", "") or decision.model_type).strip().lower()
    type_code = int(getattr(model, "model_type", decision.model_type_code) or decision.model_type_code)
    if classification not in _MODEL_TYPE_CODES:
        classification = _MODEL_TYPES.get(type_code, classification or "character")
    decision = replace(
        decision,
        model_type=classification,
        model_type_code=type_code,
        model_workflow=_workflow_for_loaded_model(model, classification),
    )
    model._gr_import_decision = decision.to_dict()
    model._gr_import_method = decision.import_method
    model._gr_import_game_evidence = decision.game_evidence
    model._gr_model_workflow = decision.model_workflow
    return model


def _decision_for_bytes(
    path: Path,
    raw: bytes,
    *,
    mdx_path: str | Path,
    game_hint: str,
    fallback_game: str,
    k1_root: str | Path,
    k2_root: str | Path,
) -> MdlImportDecision:
    source_format = _detect_source_format(raw)
    resolved_mdx = _resolve_mdx_path(path, mdx_path) if source_format == "binary" else None
    game, confidence, evidence, platform = _detect_game(
        path,
        raw,
        source_format=source_format,
        game_hint=game_hint,
        fallback_game=fallback_game,
        k1_root=k1_root,
        k2_root=k2_root,
    )
    model_type, model_type_code = _detect_model_type(raw, source_format)
    return MdlImportDecision(
        source_path=str(path),
        source_format=source_format,
        import_method="binary MDL/MDX loader" if source_format == "binary" else "ASCII MDL loader",
        game=game,
        game_confidence=confidence,
        game_evidence=evidence,
        model_type=model_type,
        model_type_code=model_type_code,
        model_workflow=_MODEL_WORKFLOWS.get(model_type, "generic_model"),
        mdx_path=str(resolved_mdx) if resolved_mdx is not None else "",
        platform=platform,
    )


def _validated_mdl_path(value: str | Path) -> Path:
    path = Path(value).expanduser().resolve()
    if not path.is_file():
        raise FileNotFoundError(path)
    if path.suffix.lower() != ".mdl":
        raise ValueError(f"Expected a .mdl file, received {path.name}")
    return path


def _detect_source_format(raw: bytes) -> str:
    try:
        detected = detect_mdl(raw)
        if detected == ResourceType.MDL_ASCII:
            return "ascii"
        if detected == ResourceType.MDL:
            return "binary"
    except Exception:
        pass
    prefix = raw[:256].lstrip(b"\xef\xbb\xbf\x00\t\r\n ").lower()
    return "ascii" if prefix.startswith((b"newmodel", b"#")) else "binary"


def _detect_game(
    path: Path,
    raw: bytes,
    *,
    source_format: str,
    game_hint: str,
    fallback_game: str,
    k1_root: str | Path,
    k2_root: str | Path,
) -> tuple[str, str, str, str]:
    hint = _normalize_game(game_hint, allow_empty=True)
    if hint:
        return hint, "explicit", "caller supplied game", "PC"

    if source_format == "binary" and len(raw) >= 16:
        fp1 = struct.unpack_from("<I", raw, 12)[0]
        if fp1 in _K2_FUNCTION_POINTERS:
            return "K2", "exact", f"K2 geometry function pointer 0x{fp1:08X}", "Xbox" if fp1 == 4285872 else "PC"
        if fp1 in _K1_FUNCTION_POINTERS:
            return "K1", "exact", f"K1 geometry function pointer 0x{fp1:08X}", "Xbox" if fp1 == 4254992 else "PC"

    for game, root in (("K1", k1_root), ("K2", k2_root)):
        if root and _is_under(path, Path(root).expanduser()):
            return game, "path", f"file is inside configured {game} installation", "PC"

    if source_format == "ascii":
        text = raw[:8192].decode("utf-8", errors="ignore")
        match = re.search(r"(?im)^\s*#.*?\b(?:game\s*[:=]?\s*)?(kotor\s*(?:ii|2)|tsl|kotor\s*(?:i|1))\b", text)
        if match:
            token = match.group(1).lower()
            game = "K2" if ("ii" in token or "2" in token or "tsl" in token) else "K1"
            return game, "metadata", "ASCII MDL header comment", "PC"

    fallback = _normalize_game(fallback_game, allow_empty=False)
    reason = "ASCII MDL has no binary game signature" if source_format == "ascii" else "unrecognized binary function pointer"
    return fallback, "fallback", f"{reason}; used configured default", "PC"


def _detect_model_type(raw: bytes, source_format: str) -> tuple[str, int]:
    if source_format == "binary" and len(raw) >= 93:
        code = int(raw[92])
        return _MODEL_TYPES.get(code, "character"), code
    text = raw[:16384].decode("utf-8", errors="ignore")
    match = re.search(r"(?im)^\s*classification\s+(\S+)", text)
    name = match.group(1).strip().lower() if match else "character"
    code = _MODEL_TYPE_CODES.get(name, 4)
    return _MODEL_TYPES.get(code, name), code


def _workflow_for_loaded_model(model, classification: str) -> str:
    """Choose the product workflow using parsed topology plus classification."""

    try:
        nodes = list(model.all_nodes())
    except Exception:
        nodes = []
    if any(bool(getattr(node, "is_aabb", False)) for node in nodes):
        return "area_model"
    if any(bool(getattr(node, "is_skin", False)) for node in nodes):
        return "character_model"
    return _MODEL_WORKFLOWS.get(classification, "generic_model")


def _resolve_mdx_path(mdl_path: Path, requested: str | Path) -> Path | None:
    if requested:
        candidate = Path(requested).expanduser().resolve()
        if candidate.is_file():
            return candidate
    direct = mdl_path.with_suffix(".mdx")
    if direct.is_file():
        return direct
    try:
        for candidate in mdl_path.parent.iterdir():
            if candidate.is_file() and candidate.stem.lower() == mdl_path.stem.lower() and candidate.suffix.lower() == ".mdx":
                return candidate.resolve()
    except OSError:
        pass
    return None


def _normalize_game(value: str, *, allow_empty: bool) -> str:
    text = str(value or "").strip().upper().replace(" ", "")
    if allow_empty and text in {"", "AUTO", "AUTOMATIC"}:
        return ""
    if text in {"K2", "2", "KOTOR2", "KOTORII", "TSL"}:
        return "K2"
    return "K1"


def _is_under(path: Path, root: Path) -> bool:
    try:
        path.resolve().relative_to(root.resolve())
        return True
    except (OSError, ValueError):
        return False


def _report(callback, message: str, step: int, total: int) -> None:
    if callback is not None:
        callback(message, step, total)
