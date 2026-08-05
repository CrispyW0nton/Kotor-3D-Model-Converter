"""Template-led UTC behavior authoring for the Custom Character Builder.

The workflow copies a selected installed UTC in memory, preserves all unknown
fields, and records only explicit hook overrides in the project.  Custom NSS is
compiled through the shared Scripting Studio service and parsed back before it
may enter a package; retail-engine behavior still requires the visible game
smoke test.
"""

from __future__ import annotations

import hashlib
import io
import re
import wave
from dataclasses import dataclass, field
from typing import Any, Mapping

from src.core.project.custom_rigged_character_project import (
    CUSTOM_CREATURE_BEHAVIOR_PROFILE_SCHEMA,
    CreatureSoundCue,
    CustomRiggedCharacterProject,
)
from src.resources.kotor_utc_template_catalog import (
    UTC_SCRIPT_HOOK_FIELDS,
    InstalledUtcTemplateCatalog,
    UtcTemplateSummary,
)


BEHAVIOR_BUILD_SCHEMA = "ghostrigger.custom_creature_behavior_build.v1"
_RESREF = re.compile(r"^[a-z0-9_]{1,16}$")

CREATURE_SOUND_CUE_DEFINITIONS: dict[str, dict[str, Any]] = {
    "roar": {
        "label": "Combat roar",
        "ssf_slots": ("BATTLE_CRY_1",),
        "patterns": ("roar", "combatyell", "battlecry"),
        "resref_suffix": "roar",
    },
    "attack": {
        "label": "Attack vocal",
        "ssf_slots": ("ATTACK_GRUNT_1", "ATTACK_GRUNT_2", "ATTACK_GRUNT_3"),
        "patterns": ("runattack", "attack", "headbutt"),
        "resref_suffix": "vatk",
    },
    "hurt": {
        "label": "Pain / damage",
        "ssf_slots": ("PAIN_GRUNT_1",),
        "patterns": ("gethit", "hurt", "pain"),
        "resref_suffix": "hurt",
    },
    "guard": {
        "label": "Defensive combat vocal",
        "ssf_slots": ("BATTLE_CRY_2",),
        "patterns": ("defensemode", "guard", "defense"),
        "resref_suffix": "guard",
    },
    "blocked": {
        "label": "Blocked / wall impact",
        "ssf_slots": ("PAIN_GRUNT_2",),
        "patterns": ("hitwall", "blocked", "impact"),
        "resref_suffix": "wall",
    },
    "idle": {
        "label": "Low-health breathing",
        "ssf_slots": ("LOW_HEALTH",),
        "patterns": ("breathe", "breath", "idle"),
        "resref_suffix": "breath",
    },
    "death": {
        "label": "Death vocal",
        "ssf_slots": ("DEAD",),
        "patterns": ("death", "die", "dead"),
        "resref_suffix": "death",
    },
}

UTC_SCRIPT_HOOK_LABELS = {
    "ScriptHeartbeat": "Heartbeat",
    "ScriptOnNotice": "Notices another creature",
    "ScriptSpellAt": "Targeted by a power",
    "ScriptAttacked": "Attacked",
    "ScriptDamaged": "Damaged",
    "ScriptDisturbed": "Inventory disturbed",
    "ScriptEndRound": "Combat round ends",
    "ScriptEndDialogu": "Conversation ends",
    "ScriptDialogue": "Conversation requested",
    "ScriptSpawn": "Spawned",
    "ScriptRested": "Rested",
    "ScriptDeath": "Dies",
    "ScriptUserDefine": "User-defined event",
    "ScriptOnBlocked": "Movement blocked",
}


def _clean_resref(value: Any, label: str = "Script") -> str:
    text = str(value or "").strip().lower()
    if text.endswith((".nss", ".ncs")):
        text = text.rsplit(".", 1)[0]
    if not _RESREF.fullmatch(text):
        raise ValueError(f"{label} name must use 1-16 lowercase letters, numbers, or underscores.")
    return text


def creature_sound_resref(project: CustomRiggedCharacterProject, cue: str) -> str:
    definition = CREATURE_SOUND_CUE_DEFINITIONS.get(str(cue or "").strip().lower())
    if definition is None:
        raise ValueError(f"Unknown creature sound cue: {cue}")
    base = _clean_resref(project.resource_name, "Creature resource")
    suffix = str(definition["resref_suffix"])
    return _clean_resref(f"{base[:16 - len(suffix) - 1]}_{suffix}", "Creature sound")


def _wav_summary(data: bytes, label: str) -> dict[str, Any]:
    try:
        with wave.open(io.BytesIO(data), "rb") as stream:
            channels = int(stream.getnchannels())
            sample_width = int(stream.getsampwidth())
            sample_rate = int(stream.getframerate())
            frame_count = int(stream.getnframes())
            compression = str(stream.getcomptype())
    except (EOFError, wave.Error) as exc:
        raise ValueError(f"{label} is not a readable PCM WAV file: {exc}") from exc
    if compression != "NONE" or channels != 1 or sample_width != 2:
        raise ValueError(f"{label} must be an uncompressed mono 16-bit PCM WAV file for KOTOR.")
    if sample_rate not in {11025, 22050, 44100}:
        raise ValueError(f"{label} uses unsupported sample rate {sample_rate}; use 11025, 22050, or 44100 Hz.")
    if frame_count <= 0:
        raise ValueError(f"{label} contains no audio frames.")
    return {
        "sample_rate": sample_rate,
        "channels": channels,
        "bits_per_sample": sample_width * 8,
        "frame_count": frame_count,
        "duration_seconds": frame_count / float(sample_rate),
    }


def behavior_starter_source(hook: str, inherited_script: str = "") -> str:
    if hook not in UTC_SCRIPT_HOOK_FIELDS:
        raise ValueError(f"Unknown UTC behavior hook: {hook}")
    event = UTC_SCRIPT_HOOK_LABELS.get(hook, hook)
    inherited = str(inherited_script or "").strip().lower()
    preserved = f'    ExecuteScript("{inherited}", OBJECT_SELF);\n' if inherited else ""
    return (
        "// Generated starter by Ghost Studio Character Builder.\n"
        f"// UTC event: {event}.\n"
        "// The installed template behavior runs first. Add only the extra\n"
        "// actions you need beneath it, then use Compile and check.\n"
        "void main()\n"
        "{\n"
        f"{preserved}"
        "    // Add custom KOTOR actions here.\n"
        "}\n"
    )


def spawn_test_script_resref(project: CustomRiggedCharacterProject) -> str:
    """Return a deterministic KOTOR-safe name for the optional spawn helper."""

    utc_resref = str(project.utc_settings.get("resref") or project.resource_name).strip().lower()
    candidate = f"spawn_{utc_resref}"
    return candidate if len(candidate) <= 16 else f"sp_{utc_resref[:13]}"


def spawn_test_script_source(project: CustomRiggedCharacterProject) -> str:
    """Return the auditable test helper compiled by the Character Builder."""

    utc_resref = _clean_resref(
        project.utc_settings.get("resref") or project.resource_name,
        "UTC resource",
    )
    return (
        "// Ghost Studio test spawn. Generated and compiled for the selected game.\n"
        "void main()\n"
        "{\n"
        f'    CreateObject(OBJECT_TYPE_CREATURE, "{utc_resref}", GetLocation(OBJECT_SELF));\n'
        "}\n"
    )


@dataclass(frozen=True)
class BehaviorHookCompileResult:
    ok: bool
    hook: str
    resref: str
    source: str
    ncs_bytes: bytes = b""
    diagnostics: tuple[Mapping[str, Any], ...] = ()

    @property
    def ncs_sha256(self) -> str:
        return hashlib.sha256(self.ncs_bytes).hexdigest() if self.ncs_bytes else ""

    def to_dict(self, *, include_source: bool = True) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "hook": self.hook,
            "resref": self.resref,
            "source": self.source if include_source else "",
            "source_sha256": hashlib.sha256(self.source.encode("utf-8")).hexdigest(),
            "ncs_sha256": self.ncs_sha256,
            "diagnostics": [dict(value) for value in self.diagnostics],
        }


@dataclass(frozen=True)
class BehaviorBuildPreparation:
    ok: bool
    utc_template_bytes: bytes = b""
    resources: tuple[tuple[str, str, bytes], ...] = ()
    utc_hook_overrides: Mapping[str, str] = field(default_factory=dict)
    report: Mapping[str, Any] = field(default_factory=dict)
    error: str = ""


class CustomRiggedCharacterBehaviorService:
    """Apply installed templates and prepare auditable UTC behavior resources."""

    @staticmethod
    def apply_template(
        project: CustomRiggedCharacterProject,
        template: UtcTemplateSummary,
        *,
        clear_explicit_hooks: bool = True,
    ) -> None:
        if template.game.upper() != project.target_game.upper():
            raise ValueError(
                f"{template.resref}.utc is a {template.game} template, but this project targets {project.target_game}."
            )
        hooks = {} if clear_explicit_hooks else dict(project.behavior_profile.get("script_hooks") or {})
        project.behavior_profile = {
            "schema": CUSTOM_CREATURE_BEHAVIOR_PROFILE_SCHEMA,
            "template_game": template.game,
            "template_resref": template.resref,
            "template_display_name": template.display_name,
            "template_source": template.source,
            "template_sha256": template.sha256,
            "inherit_template_combat_stats": True,
            "template_snapshot": template.to_dict(),
            "script_hooks": hooks,
        }
        project.gameplay_settings["behavior_preset"] = "installed_utc_template"
        project.gameplay_settings["faction"] = {
            1: "Hostile",
            2: "Friendly",
            5: "Neutral",
        }.get(template.faction_id, "Custom")
        project.gameplay_settings["perception_range"] = float(max(0, template.perception_range))
        project.gameplay_settings["soundset"] = str(max(0, template.soundset))

    @staticmethod
    def set_inherit_hook(project: CustomRiggedCharacterProject, hook: str) -> None:
        if hook not in UTC_SCRIPT_HOOK_FIELDS:
            raise ValueError(f"Unknown UTC behavior hook: {hook}")
        hooks = dict(project.behavior_profile.get("script_hooks") or {})
        hooks.pop(hook, None)
        project.behavior_profile["script_hooks"] = hooks

    @staticmethod
    def set_existing_hook(
        project: CustomRiggedCharacterProject,
        hook: str,
        resref: str,
    ) -> None:
        if hook not in UTC_SCRIPT_HOOK_FIELDS:
            raise ValueError(f"Unknown UTC behavior hook: {hook}")
        clean = _clean_resref(resref, UTC_SCRIPT_HOOK_LABELS.get(hook, "Script"))
        hooks = dict(project.behavior_profile.get("script_hooks") or {})
        hooks[hook] = {"mode": "existing", "resref": clean}
        project.behavior_profile["script_hooks"] = hooks

    def compile_custom_hook(
        self,
        *,
        game: str,
        hook: str,
        resref: str,
        source: str,
    ) -> BehaviorHookCompileResult:
        if hook not in UTC_SCRIPT_HOOK_FIELDS:
            raise ValueError(f"Unknown UTC behavior hook: {hook}")
        clean = _clean_resref(resref, UTC_SCRIPT_HOOK_LABELS.get(hook, "Script"))
        # Scripting Studio's package also owns optional SQLite-backed project
        # history.  Load it only when the user explicitly compiles a hook so
        # ordinary Ghost Studio startup and UTC browsing do not depend on that
        # native extension being initialized.
        from src.core.scripting.studio import ScriptDocument, ScriptingStudioService

        result = ScriptingStudioService().compile_script(
            ScriptDocument(resref=clean, game=game, source=str(source or ""), origin="character_builder")
        )
        diagnostics = tuple(value.to_dict() for value in result.diagnostics)
        return BehaviorHookCompileResult(
            ok=result.ok,
            hook=hook,
            resref=clean,
            source=str(source or ""),
            ncs_bytes=bytes(result.ncs_bytes),
            diagnostics=diagnostics,
        )

    def set_custom_hook(
        self,
        project: CustomRiggedCharacterProject,
        *,
        hook: str,
        resref: str,
        source: str,
    ) -> BehaviorHookCompileResult:
        result = self.compile_custom_hook(
            game=project.target_game,
            hook=hook,
            resref=resref,
            source=source,
        )
        if not result.ok:
            return result
        hooks = dict(project.behavior_profile.get("script_hooks") or {})
        hooks[hook] = {
            "mode": "custom",
            "resref": result.resref,
            "source": result.source,
            "source_sha256": hashlib.sha256(result.source.encode("utf-8")).hexdigest(),
            "last_compile": result.to_dict(include_source=False),
        }
        project.behavior_profile["script_hooks"] = hooks
        project.gameplay_settings["behavior_preset"] = "custom_scripts"
        return result

    def prepare_build(
        self,
        project: CustomRiggedCharacterProject,
        catalog: InstalledUtcTemplateCatalog | None,
    ) -> BehaviorBuildPreparation:
        profile = dict(project.behavior_profile or {})
        template_resref = str(profile.get("template_resref") or "").strip().lower()
        try:
            template: UtcTemplateSummary | None = None
            source = b""
            template_hash = ""
            if template_resref:
                if catalog is None:
                    raise ValueError("Refresh or resolve the installed UTC template before building.")
                template = catalog.get(template_resref)
                source = catalog.read_template_bytes(template_resref)
                expected_hash = str(profile.get("template_sha256") or "").strip().lower()
                template_hash = hashlib.sha256(source).hexdigest()
                if expected_hash and expected_hash != template_hash:
                    raise ValueError(
                        f"Installed template {template_resref}.utc changed since selection. Refresh and review it again."
                    )
                if template.game.upper() != project.target_game.upper():
                    raise ValueError("Selected UTC template belongs to the other KOTOR game.")

            resources: dict[tuple[str, str], bytes] = {}
            utc_hook_overrides: dict[str, str] = {}
            compile_rows: list[dict[str, Any]] = []
            custom_source_by_resref: dict[str, str] = {}
            for hook, row_value in sorted(dict(profile.get("script_hooks") or {}).items()):
                if hook not in UTC_SCRIPT_HOOK_FIELDS:
                    raise ValueError(f"Project contains an unknown UTC behavior hook: {hook}")
                row = dict(row_value or {})
                mode = str(row.get("mode") or "inherit").strip().lower()
                if mode == "inherit":
                    continue
                resref = _clean_resref(row.get("resref"), UTC_SCRIPT_HOOK_LABELS.get(hook, "Script"))
                if mode == "existing":
                    compile_rows.append({"hook": hook, "mode": mode, "resref": resref, "compiled": False})
                    continue
                if mode != "custom":
                    raise ValueError(f"Unknown behavior hook mode '{mode}' for {hook}.")
                source_text = str(row.get("source") or "")
                previous = custom_source_by_resref.get(resref)
                if previous is not None and previous != source_text:
                    raise ValueError(f"Custom script name {resref} is reused with different source code.")
                custom_source_by_resref[resref] = source_text
                result = self.compile_custom_hook(
                    game=project.target_game,
                    hook=hook,
                    resref=resref,
                    source=source_text,
                )
                compile_rows.append({"hook": hook, "mode": mode, **result.to_dict(include_source=False)})
                if not result.ok:
                    message = next(
                        (str(value.get("message")) for value in result.diagnostics if value.get("severity") in {"blocking", "error"}),
                        "NWScript compilation failed.",
                    )
                    raise ValueError(f"{UTC_SCRIPT_HOOK_LABELS.get(hook, hook)}: {message}")
                resources[(resref, "nss")] = source_text.encode("utf-8")
                resources[(resref, "ncs")] = result.ncs_bytes

            sound_rows: list[dict[str, Any]] = []
            seen_cues: set[str] = set()
            for cue_value in project.creature_sound_cues:
                cue = cue_value if isinstance(cue_value, CreatureSoundCue) else CreatureSoundCue.from_dict(cue_value)
                cue_name = str(cue.cue or "").strip().lower()
                definition = CREATURE_SOUND_CUE_DEFINITIONS.get(cue_name)
                if definition is None:
                    raise ValueError(f"Project contains unknown creature sound cue '{cue_name}'.")
                if cue_name in seen_cues:
                    raise ValueError(f"Creature sound cue '{cue_name}' is assigned more than once.")
                seen_cues.add(cue_name)
                source_path = project.resolve_path(cue.source_path)
                if not source_path.is_file():
                    raise ValueError(f"{definition['label']} sound file was not found: {source_path}")
                payload = source_path.read_bytes()
                audio_hash = hashlib.sha256(payload).hexdigest()
                if cue.source_sha256 and cue.source_sha256 != audio_hash:
                    raise ValueError(f"{definition['label']} sound changed since it was selected. Choose it again.")
                audio_resref = _clean_resref(
                    cue.output_resref or creature_sound_resref(project, cue_name),
                    "Creature sound",
                )
                wav = _wav_summary(payload, str(definition["label"]))
                resources[(audio_resref, "wav")] = payload
                sound_rows.append({
                    "cue": cue_name,
                    "label": definition["label"],
                    "ssf_slots": list(definition["ssf_slots"]),
                    "resref": audio_resref,
                    "sha256": audio_hash,
                    "size": len(payload),
                    **wav,
                })

            spawn_report: dict[str, Any] | None = None
            if bool(project.gameplay_settings.get("generate_spawn_script")):
                spawn_resref = spawn_test_script_resref(project)
                spawn_source = spawn_test_script_source(project)
                spawn_result = self.compile_custom_hook(
                    game=project.target_game,
                    hook="ScriptSpawn",
                    resref=spawn_resref,
                    source=spawn_source,
                )
                if not spawn_result.ok:
                    message = next(
                        (
                            str(value.get("message"))
                            for value in spawn_result.diagnostics
                            if value.get("severity") in {"blocking", "error"}
                        ),
                        "Test-spawn NWScript compilation failed.",
                    )
                    raise ValueError(f"Test-spawn helper: {message}")
                resources[(spawn_resref, "nss")] = spawn_source.encode("utf-8")
                resources[(spawn_resref, "ncs")] = spawn_result.ncs_bytes
                spawn_report = spawn_result.to_dict(include_source=False)

            report = {
                "schema": BEHAVIOR_BUILD_SCHEMA,
                "template": ({
                    "game": template.game,
                    "resref": template.resref,
                    "display_name": template.display_name,
                    "source": template.source,
                    "sha256": template_hash,
                    "module_only_script_hooks": list(template.module_only_script_hooks),
                } if template is not None else None),
                "inherit_template_combat_stats": bool(profile.get("inherit_template_combat_stats", True)),
                "custom_hooks": compile_rows,
                "creature_sounds": {
                    "cues": sound_rows,
                    "delivery": "native_ssf_soundset",
                    "hook_wrappers": [],
                    "preserves_direct_utc_event_hooks": True,
                    "requires_merge_safe_dialog_tlk_append": bool(sound_rows),
                    "requires_merge_safe_soundset_2da_row": bool(sound_rows),
                },
                "test_spawn_script": spawn_report,
                "retail_game_proof_required": True,
            }
            return BehaviorBuildPreparation(
                ok=True,
                utc_template_bytes=source,
                resources=tuple((resref, restype, value) for (resref, restype), value in sorted(resources.items())),
                utc_hook_overrides=utc_hook_overrides,
                report=report,
            )
        except Exception as exc:
            return BehaviorBuildPreparation(ok=False, error=str(exc))


__all__ = [
    "BEHAVIOR_BUILD_SCHEMA",
    "BehaviorBuildPreparation",
    "BehaviorHookCompileResult",
    "CREATURE_SOUND_CUE_DEFINITIONS",
    "CustomRiggedCharacterBehaviorService",
    "UTC_SCRIPT_HOOK_LABELS",
    "behavior_starter_source",
    "creature_sound_resref",
    "spawn_test_script_resref",
    "spawn_test_script_source",
]
