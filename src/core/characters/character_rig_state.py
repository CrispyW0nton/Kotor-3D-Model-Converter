"""Character Builder rig-state markers.

The Character Builder has two very different skeleton states:

* imported/external skeletons used only as temporary fit information;
* the final native KOTOR template skeleton used for game export.

This module keeps those flags in headless core code so Qt panels can orchestrate
the workflow without owning KOTOR export rules.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


RIG_STATE_IMPORTED_TEMPORARY = "imported_temporary_skeleton"
RIG_STATE_NATIVE_TEMPLATE_FINAL = "native_template_final"
RIG_DAG_AUTHORITY_IMPORTED = "imported_external_skeleton"
RIG_DAG_AUTHORITY_NATIVE_KOTOR = "native_kotor_base"
MESH_ROLE_PAYLOAD_GUEST = "payload_guest"


@dataclass(frozen=True)
class CharacterRigState:
    """JSON-friendly state describing what owns a Character Builder rig."""

    state: str
    dag_authority: str
    mesh_role: str = MESH_ROLE_PAYLOAD_GUEST
    source: str = ""
    native_snapshot_present: bool = False
    legacy_acurig: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "state": self.state,
            "dag_authority": self.dag_authority,
            "mesh_role": self.mesh_role,
            "source": self.source,
            "native_snapshot_present": bool(self.native_snapshot_present),
            "legacy_acurig": bool(self.legacy_acurig),
        }


def mark_imported_temporary_skeleton(model: Any, *, source: str = "") -> CharacterRigState:
    """Mark a loaded external model as non-authoritative fit/input data."""

    state = CharacterRigState(
        state=RIG_STATE_IMPORTED_TEMPORARY,
        dag_authority=RIG_DAG_AUTHORITY_IMPORTED,
        source=source,
        native_snapshot_present=False,
        legacy_acurig=False,
    )
    _write_state(model, state)
    return state


def mark_native_template_final_rig(
    model: Any,
    *,
    source: str = "apply_template_rig",
    native_snapshot_present: bool = False,
) -> CharacterRigState:
    """Mark a generated model as using the native KOTOR template DAG."""

    state = CharacterRigState(
        state=RIG_STATE_NATIVE_TEMPLATE_FINAL,
        dag_authority=RIG_DAG_AUTHORITY_NATIVE_KOTOR,
        source=source,
        native_snapshot_present=bool(native_snapshot_present),
        legacy_acurig=False,
    )
    _write_state(model, state)
    return state


def get_character_rig_state(model: Any) -> CharacterRigState | None:
    """Return the Character Builder rig-state marker, if one is present."""

    direct = getattr(model, "_gr_character_builder_rig_state", None)
    if isinstance(direct, CharacterRigState):
        return direct
    if isinstance(direct, dict):
        return _state_from_dict(direct)
    metadata = getattr(model, "metadata", None)
    if isinstance(metadata, dict):
        raw = metadata.get("character_builder_rig_state")
        if isinstance(raw, CharacterRigState):
            return raw
        if isinstance(raw, dict):
            return _state_from_dict(raw)
    return None


def is_native_template_final_rig(model: Any) -> bool:
    """Return True only when the model is marked as final native-template rig."""

    state = get_character_rig_state(model)
    if state is None:
        return False
    return (
        state.state == RIG_STATE_NATIVE_TEMPLATE_FINAL
        and state.dag_authority == RIG_DAG_AUTHORITY_NATIVE_KOTOR
        and state.mesh_role == MESH_ROLE_PAYLOAD_GUEST
        and not state.legacy_acurig
    )


def is_imported_temporary_skeleton(model: Any) -> bool:
    """Return True when the model is only imported fit/source skeleton data."""

    state = get_character_rig_state(model)
    if state is None:
        return False
    return (
        state.state == RIG_STATE_IMPORTED_TEMPORARY
        and state.dag_authority == RIG_DAG_AUTHORITY_IMPORTED
        and state.mesh_role == MESH_ROLE_PAYLOAD_GUEST
    )


def _write_state(model: Any, state: CharacterRigState) -> None:
    if model is None:
        return
    setattr(model, "_gr_character_builder_rig_state", state)
    setattr(model, "_gr_character_builder_dag_authority", state.dag_authority)
    metadata = getattr(model, "metadata", None)
    if not isinstance(metadata, dict):
        metadata = {}
        setattr(model, "metadata", metadata)
    metadata["character_builder_rig_state"] = state.to_dict()


def _state_from_dict(data: dict[str, Any]) -> CharacterRigState:
    return CharacterRigState(
        state=str(data.get("state") or ""),
        dag_authority=str(data.get("dag_authority") or ""),
        mesh_role=str(data.get("mesh_role") or MESH_ROLE_PAYLOAD_GUEST),
        source=str(data.get("source") or ""),
        native_snapshot_present=bool(data.get("native_snapshot_present")),
        legacy_acurig=bool(data.get("legacy_acurig")),
    )
