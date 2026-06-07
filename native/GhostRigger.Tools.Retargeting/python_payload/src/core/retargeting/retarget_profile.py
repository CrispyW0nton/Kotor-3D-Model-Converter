"""Retarget profile data and JSON persistence for source-to-Aurora mapping."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
import json
from pathlib import Path
from typing import Any, Dict, List, Optional


RETARGET_PROFILE_VERSION = 1


@dataclass
class RetargetMappingEntry:
    """One semantic source-to-target mapping entry."""

    role: str
    source_node: str
    target_node: str
    side: Optional[str] = None
    allow_translation: bool = False
    allow_helper_mapping: bool = False
    notes: str = ""


@dataclass
class RetargetProfile:
    """Serializable retargeting profile connecting source nodes to Aurora nodes."""

    version: int = RETARGET_PROFILE_VERSION
    name: str = ""
    source_clip_hint: Optional[str] = None
    target_model_hint: Optional[str] = None
    animation_slot: Optional[str] = None
    source_reference: Dict[str, Any] = field(default_factory=lambda: {"mode": "clip_rest"})
    target_reference: Dict[str, Any] = field(default_factory=lambda: {"mode": "target_rest"})
    mappings: List[RetargetMappingEntry] = field(default_factory=list)
    ignored_source_nodes: List[str] = field(default_factory=list)
    twist_sources: Dict[str, List[str]] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)


def normalize_retarget_profile(profile: RetargetProfile) -> RetargetProfile:
    """Return a normalized copy while preserving names and metadata."""

    if int(profile.version) != RETARGET_PROFILE_VERSION:
        raise ValueError(
            f"Unsupported retarget profile version {profile.version}; "
            f"expected {RETARGET_PROFILE_VERSION}."
        )

    return RetargetProfile(
        version=RETARGET_PROFILE_VERSION,
        name=str(profile.name or "").strip(),
        source_clip_hint=_optional_str(profile.source_clip_hint),
        target_model_hint=_optional_str(profile.target_model_hint),
        animation_slot=_optional_str(profile.animation_slot),
        source_reference=dict(profile.source_reference or {"mode": "clip_rest"}),
        target_reference=dict(profile.target_reference or {"mode": "target_rest"}),
        mappings=[
            RetargetMappingEntry(
                role=str(entry.role or "").strip(),
                source_node=str(entry.source_node or "").strip(),
                target_node=str(entry.target_node or "").strip(),
                side=_optional_str(entry.side),
                allow_translation=bool(entry.allow_translation),
                allow_helper_mapping=bool(entry.allow_helper_mapping),
                notes=str(entry.notes or ""),
            )
            for entry in list(profile.mappings or [])
        ],
        ignored_source_nodes=[str(name or "").strip() for name in list(profile.ignored_source_nodes or [])],
        twist_sources={
            str(target or "").strip(): [str(name or "").strip() for name in list(names or [])]
            for target, names in dict(profile.twist_sources or {}).items()
        },
        metadata=dict(profile.metadata or {}),
    )


def load_retarget_profile(path: str | Path) -> RetargetProfile:
    """Load a retarget profile JSON file."""

    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    mappings = [
        RetargetMappingEntry(
            role=str(item.get("role", "")),
            source_node=str(item.get("source_node", "")),
            target_node=str(item.get("target_node", "")),
            side=item.get("side"),
            allow_translation=bool(item.get("allow_translation", False)),
            allow_helper_mapping=bool(item.get("allow_helper_mapping", False)),
            notes=str(item.get("notes", "")),
        )
        for item in list(payload.get("mappings", []) or [])
    ]
    profile = RetargetProfile(
        version=int(payload.get("version", RETARGET_PROFILE_VERSION)),
        name=str(payload.get("name", "")),
        source_clip_hint=payload.get("source_clip_hint"),
        target_model_hint=payload.get("target_model_hint"),
        animation_slot=payload.get("animation_slot"),
        source_reference=dict(payload.get("source_reference") or {"mode": "clip_rest"}),
        target_reference=dict(payload.get("target_reference") or {"mode": "target_rest"}),
        mappings=mappings,
        ignored_source_nodes=list(payload.get("ignored_source_nodes") or []),
        twist_sources=dict(payload.get("twist_sources") or {}),
        metadata=dict(payload.get("metadata") or {}),
    )
    return normalize_retarget_profile(profile)


def save_retarget_profile(profile: RetargetProfile, path: str | Path) -> None:
    """Save a retarget profile as stable, indented JSON."""

    normalized = normalize_retarget_profile(profile)
    out_path = Path(path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(
        json.dumps(asdict(normalized), indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _optional_str(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    text = str(value).strip()
    return text or None
