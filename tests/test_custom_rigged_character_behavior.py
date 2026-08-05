from __future__ import annotations

import hashlib
import json
import wave
from pathlib import Path
from types import SimpleNamespace

import pytest

from pykotor.common.language import LocalizedString
from pykotor.resource.formats.gff import GFF, GFFContent, GFFList, bytes_gff, read_gff
from pykotor.resource.formats.ssf import SSFSound
from pykotor.resource.type import ResourceType

from src.core.characters.custom_rigged_character_behavior_service import (
    CustomRiggedCharacterBehaviorService,
    behavior_starter_source,
    spawn_test_script_resref,
    spawn_test_script_source,
)
from src.core.characters.custom_rigged_character_packaging_service import (
    CustomRiggedCharacterPackagingService,
)
from src.core.scripting.data_authoring import SoundSetDocument, TalkTableDocument
from src.core.templates.twoda import TwoDA
from src.core.project.custom_rigged_character_project import (
    CURRENT_CUSTOM_RIGGED_CHARACTER_SCHEMA_VERSION,
    CUSTOM_CREATURE_BEHAVIOR_PROFILE_SCHEMA,
    CreatureSoundCue,
    CustomRiggedCharacterProject,
    migrate_custom_rigged_character_payload,
)
from src.resources.kotor_utc_template_catalog import InstalledUtcTemplateCatalog


ROOT = Path(__file__).resolve().parents[1]


def test_behavior_service_defers_scripting_studio_until_compile() -> None:
    source = (
        ROOT
        / "native"
        / "GhostRigger.Core.Workflow"
        / "Python"
        / "src"
        / "core"
        / "characters"
        / "custom_rigged_character_behavior_service.py"
    ).read_text(encoding="utf-8")

    import_line = "from src.core.scripting.studio import ScriptDocument, ScriptingStudioService"
    assert import_line not in source.split("BEHAVIOR_BUILD_SCHEMA", 1)[0]
    assert import_line in source.split("def compile_custom_hook", 1)[1]


def _utc_bytes(
    resref: str,
    *,
    name: str,
    spawn: str = "k_def_ambmob",
    attacked: str = "k_def_attacked01",
    module_script: str = "",
) -> bytes:
    gff = GFF(GFFContent.UTC)
    root = gff.root
    root.set_resref("TemplateResRef", resref)
    root.set_string("Tag", resref)
    root.set_locstring("FirstName", LocalizedString.from_english(name))
    root.set_uint16("Appearance_Type", 605)
    root.set_uint16("FactionID", 1)
    root.set_uint16("SoundSetFile", 31)
    root.set_uint8("Str", 18)
    root.set_uint8("Dex", 14)
    root.set_uint8("Con", 16)
    root.set_uint8("Int", 3)
    root.set_uint8("Wis", 3)
    root.set_uint8("Cha", 6)
    root.set_int16("HitPoints", 70)
    root.set_int16("CurrentHitPoints", 70)
    root.set_int16("MaxHitPoints", 97)
    root.set_single("ChallengeRating", 9.0)
    root.set_uint8("PerceptionRange", 11)
    root.set_int32("WalkRate", 7)
    root.set_resref("ScriptHeartbeat", "k_def_heartbt01")
    root.set_resref("ScriptAttacked", attacked)
    root.set_resref("ScriptSpawn", module_script or spawn)
    root.set_resref("ScriptDeath", "k_def_death01")
    root.set_string("GhostUnknown", "preserve-this-field")
    classes = GFFList()
    creature_class = classes.add(2)
    creature_class.set_uint8("Class", 8)
    creature_class.set_uint8("ClassLevel", 9)
    root.set_list("ClassList", classes)
    equipment = GFFList()
    weapon = equipment.add(16384)
    weapon.set_resref("EquippedRes", "g_w_crslash003")
    root.set_list("Equip_ItemList", equipment)
    return bytes(bytes_gff(gff))


class _FakeResource:
    def __init__(self, resref: str, restype: ResourceType, data: bytes = b"") -> None:
        self._resref = resref
        self._restype = restype
        self.data = data

    def resname(self) -> str:
        return self._resref

    def restype(self) -> ResourceType:
        return self._restype


class _FakeTalkTable:
    @staticmethod
    def string(_strref: int) -> str:
        return ""


class _FakeInstallation:
    def __init__(self, _root: Path) -> None:
        global_utc = _utc_bytes("c_zakkeg01", name="Zakkeg")
        module_utc = _utc_bytes(
            "c_zakkeg002",
            name="Zakkeg encounter",
            module_script="k_zak_spawnin",
        )
        self._global = [
            _FakeResource("c_zakkeg01", ResourceType.UTC, global_utc),
            _FakeResource("k_def_ambmob", ResourceType.NCS, b"NCS V1.0fixture"),
            _FakeResource("k_def_attacked01", ResourceType.NCS, b"NCS V1.0fixture"),
            _FakeResource("k_def_heartbt01", ResourceType.NCS, b"NCS V1.0fixture"),
            _FakeResource("k_def_death01", ResourceType.NCS, b"NCS V1.0fixture"),
        ]
        self._module = [
            _FakeResource("c_zakkeg002", ResourceType.UTC, module_utc),
            _FakeResource("k_zak_spawnin", ResourceType.NCS, b"NCS V1.0fixture"),
        ]
        self._by_name = {
            "c_zakkeg01": self._global[0],
            "c_zakkeg002": self._module[0],
        }

    @staticmethod
    def override_resources():
        return ()

    @staticmethod
    def modules_list():
        return ("402dxn.mod",)

    def module_resources(self, _name: str):
        return tuple(self._module)

    def chitin_resources(self):
        return tuple(self._global)

    def resource(self, resref, restype, order=None):
        del restype, order
        return self._by_name.get(str(resref).lower())

    @staticmethod
    def talktable():
        return _FakeTalkTable()


def _catalog(tmp_path: Path) -> InstalledUtcTemplateCatalog:
    return InstalledUtcTemplateCatalog(
        tmp_path,
        game="K2",
        installation_factory=_FakeInstallation,
    )


def test_schema_v1_migrates_to_a_versioned_behavior_profile() -> None:
    raw = CustomRiggedCharacterProject(creature_name="Old", resource_name="c_old").to_dict()
    raw["schema_version"] = 1
    raw["gameplay"].pop("behavior_profile", None)

    migrated = migrate_custom_rigged_character_payload(raw)

    assert migrated["schema_version"] == CURRENT_CUSTOM_RIGGED_CHARACTER_SCHEMA_VERSION == 3
    assert migrated["gameplay"]["behavior_profile"]["schema"] == CUSTOM_CREATURE_BEHAVIOR_PROFILE_SCHEMA
    assert migrated["gameplay"]["behavior_profile"]["script_hooks"] == {}
    assert migrated["gameplay"]["creature_sounds"] == []


def test_catalog_indexes_every_effective_utc_and_flags_module_only_hooks(tmp_path: Path) -> None:
    catalog = _catalog(tmp_path)

    entries = {row.resref: row for row in catalog.scan()}

    assert set(entries) == {"c_zakkeg01", "c_zakkeg002"}
    assert entries["c_zakkeg01"].display_name == "Zakkeg"
    assert entries["c_zakkeg01"].script_hooks["ScriptAttacked"] == "k_def_attacked01"
    assert entries["c_zakkeg01"].module_only_script_hooks == ()
    assert entries["c_zakkeg002"].module_only_script_hooks == ("ScriptSpawn",)
    assert entries["c_zakkeg01"].classes == ({"class_id": 8, "level": 9},)
    report = catalog.report()
    assert report["template_count"] == 2
    assert report["game_directory_embedded"] is False


def test_zakkeg_template_clone_preserves_combat_data_and_packages_compiled_hook(tmp_path: Path) -> None:
    catalog = _catalog(tmp_path)
    templates = {row.resref: row for row in catalog.scan()}
    project = CustomRiggedCharacterProject(
        creature_name="Borhek",
        resource_name="c_borhek",
        target_game="K2",
        output_project_folder=str(tmp_path),
        build_destination=str(tmp_path / "build"),
        appearance_settings={"donor_row": 88},
        utc_settings={"resref": "c_borhek", "display_name": "Borhek"},
    )
    service = CustomRiggedCharacterBehaviorService()
    service.apply_template(project, templates["c_zakkeg01"])
    source = behavior_starter_source("ScriptAttacked", "k_def_attacked01")
    compile_result = service.set_custom_hook(
        project,
        hook="ScriptAttacked",
        resref="bor_attacked",
        source=source,
    )
    assert compile_result.ok, compile_result.diagnostics

    prepared = service.prepare_build(project, catalog)
    assert prepared.ok, prepared.error
    assert {(resref, restype) for resref, restype, _data in prepared.resources} == {
        ("bor_attacked", "nss"),
        ("bor_attacked", "ncs"),
    }
    model = tmp_path / "model"
    model.mkdir()
    (model / "c_borhek.mdl").write_bytes(b"mdl")
    (model / "c_borhek.mdx").write_bytes(b"mdx")
    package = CustomRiggedCharacterPackagingService(process_is_running=lambda _name: False).build_package(
        project,
        {"mdl": str(model / "c_borhek.mdl"), "mdx": str(model / "c_borhek.mdx")},
        tmp_path / "package",
        utc_template_bytes=prepared.utc_template_bytes,
        behavior_resources=prepared.resources,
        behavior_report=prepared.report,
    )
    assert package.ok, package.error
    additional = Path(package.package_directory) / "additional"
    output = read_gff((additional / "c_borhek.utc.template").read_bytes()).root
    assert str(output.acquire("TemplateResRef", "")) == "c_borhek"
    assert output.acquire("Tag", "") == "c_borhek"
    assert str(output.acquire("FirstName", "")) == "Borhek"
    assert output.acquire("GhostUnknown", "") == "preserve-this-field"
    assert int(output.acquire("FactionID", -1)) == 1
    assert int(output.acquire("HitPoints", -1)) == 70
    assert int(output.acquire("MaxHitPoints", -1)) == 97
    assert str(output.acquire("ScriptHeartbeat", "")) == "k_def_heartbt01"
    assert str(output.acquire("ScriptAttacked", "")) == "bor_attacked"
    assert int(output.acquire("ClassList", GFFList())[0].acquire("Class", -1)) == 8
    assert str(output.acquire("Equip_ItemList", GFFList())[0].acquire("EquippedRes", "")) == "g_w_crslash003"
    assert (additional / "bor_attacked.nss").read_text(encoding="utf-8") == source
    assert (additional / "bor_attacked.ncs").read_bytes().startswith(b"NCS V1.0")
    report = json.loads(Path(package.report_path).read_text(encoding="utf-8"))
    assert report["behavior"]["template"]["resref"] == "c_zakkeg01"
    assert report["behavior"]["custom_hooks"][0]["hook"] == "ScriptAttacked"


def test_creature_sound_uses_native_ssf_without_wrapping_zakkeg_ai_hooks(tmp_path: Path) -> None:
    sound = tmp_path / "A1_AN_Borhek_GetHit01.wav"
    with wave.open(str(sound), "wb") as stream:
        stream.setnchannels(1)
        stream.setsampwidth(2)
        stream.setframerate(22050)
        stream.writeframes(b"\0\0" * 2205)

    catalog = _catalog(tmp_path)
    template = next(row for row in catalog.scan() if row.resref == "c_zakkeg01")
    project = CustomRiggedCharacterProject(
        creature_name="Borhek",
        resource_name="c_borhek",
        target_game="K2",
        output_project_folder=str(tmp_path),
        appearance_settings={"donor_row": 0},
        utc_settings={"resref": "c_borhek", "display_name": "Borhek", "faction_id": 1},
        creature_sound_cues=[CreatureSoundCue(
            cue="hurt",
            source_path=str(sound),
            source_sha256=hashlib.sha256(sound.read_bytes()).hexdigest(),
            output_resref="c_borhek_hurt",
        )],
    )
    service = CustomRiggedCharacterBehaviorService()
    service.apply_template(project, template)

    prepared = service.prepare_build(project, catalog)

    assert prepared.ok, prepared.error
    resources = {(resref, restype): data for resref, restype, data in prepared.resources}
    assert resources[("c_borhek_hurt", "wav")].startswith(b"RIFF")
    assert prepared.utc_hook_overrides == {}
    assert set(resources) == {("c_borhek_hurt", "wav")}
    assert prepared.report["creature_sounds"]["delivery"] == "native_ssf_soundset"
    assert prepared.report["creature_sounds"]["preserves_direct_utc_event_hooks"] is True
    assert prepared.report["creature_sounds"]["cues"][0]["ssf_slots"] == ["PAIN_GRUNT_1"]
    assert prepared.report["template"]["sha256"] == template.sha256

    model = tmp_path / "sound-model"
    model.mkdir()
    (model / "c_borhek.mdl").write_bytes(b"mdl")
    (model / "c_borhek.mdx").write_bytes(b"mdx")
    package = CustomRiggedCharacterPackagingService(process_is_running=lambda _name: False).build_package(
        project,
        {"mdl": str(model / "c_borhek.mdl"), "mdx": str(model / "c_borhek.mdx")},
        tmp_path / "sound-package",
        utc_template_bytes=prepared.utc_template_bytes,
        behavior_resources=prepared.resources,
        utc_hook_overrides=prepared.utc_hook_overrides,
        behavior_report=prepared.report,
    )
    assert package.ok, package.error
    additional = Path(package.package_directory) / "additional"
    utc = read_gff((additional / "c_borhek.utc.template").read_bytes()).root
    assert int(utc.acquire("SoundSetFile", -1)) == 31
    assert str(utc.acquire("ScriptHeartbeat", "")) == "k_def_heartbt01"
    assert str(utc.acquire("ScriptAttacked", "")) == "k_def_attacked01"
    assert str(utc.acquire("ScriptSpawn", "")) == "k_def_ambmob"
    plan = json.loads((additional / "install-plan.json").read_text(encoding="utf-8"))
    assert "c_borhek_hurt.wav" in plan["runtime_files"]
    assert plan["soundset_patch"] == "soundset.2da.patch.json"
    assert plan["requires_dialog_tlk_patch"] is True

    game = tmp_path / "KOTOR2"
    override = game / "Override"
    override.mkdir(parents=True)
    (game / "swkotor2.exe").write_bytes(b"fake-test-executable")
    (game / "dialog.tlk").write_bytes(TalkTableDocument().to_bytes())
    (override / "appearance.2da").write_bytes((
        "2DA V2.0\n\n"
        "          label             race              walkdist          rundist           perspace          creperspace       cameraspace       targetheight      hitdist           prefatckdist\n"
        "0         Creature_Donor    c_donor           1.0               2.0               0.5               0.5               0.5               0.5               0.5               0.5\n"
    ).encode("ascii"))
    (override / "soundset.2da").write_bytes((
        "2DA V2.0\n\n"
        "          label             resref            strref            gender            type\n"
        "0         None              ****              ****              ****              ****\n"
    ).encode("ascii"))
    before_dialog = (game / "dialog.tlk").read_bytes()

    preview = CustomRiggedCharacterPackagingService(
        process_is_running=lambda _name: False
    ).preview_install(package.package_directory, game)

    assert preview.ok, preview.error
    assert preview.soundset_row == 1
    assert {row["name"] for row in preview.files} >= {
        "soundset.2da",
        "c_borhek.ssf",
        "game-root/dialog.tlk",
    }
    candidate = Path(preview.candidate_directory)
    merged_utc = read_gff((candidate / "c_borhek.utc").read_bytes()).root
    assert int(merged_utc.acquire("SoundSetFile", -1)) == 1
    assert str(merged_utc.acquire("ScriptHeartbeat", "")) == "k_def_heartbt01"
    assert str(merged_utc.acquire("ScriptAttacked", "")) == "k_def_attacked01"
    merged_soundsets = TwoDA.from_bytes((candidate / "soundset.2da").read_bytes())
    assert merged_soundsets.get(1, "resref") == "c_borhek"
    merged_dialog = TalkTableDocument.load(candidate / ".global" / "dialog.tlk")
    merged_ssf = SoundSetDocument.load(candidate / "c_borhek.ssf")
    pain_strref = merged_ssf.get_slot(SSFSound.PAIN_GRUNT_1.name)
    assert pain_strref >= 0
    assert merged_dialog.entry(pain_strref).voiceover == "c_borhek_hurt"

    service = CustomRiggedCharacterPackagingService(process_is_running=lambda _name: False)
    installed = service.install(preview, confirmed_preview_id=preview.preview_id)
    assert installed.ok, installed.error
    assert (game / "dialog.tlk").read_bytes() != before_dialog
    restored = service.restore(installed.session_manifest)
    assert restored.ok, restored.error
    assert (game / "dialog.tlk").read_bytes() == before_dialog


def test_invalid_custom_hook_cannot_enter_the_project(tmp_path: Path) -> None:
    catalog = _catalog(tmp_path)
    template = next(row for row in catalog.scan() if row.resref == "c_zakkeg01")
    project = CustomRiggedCharacterProject(resource_name="c_borhek", target_game="K2")
    service = CustomRiggedCharacterBehaviorService()
    service.apply_template(project, template)

    result = service.set_custom_hook(
        project,
        hook="ScriptAttacked",
        resref="bor_bad",
        source="void main() { ThisDoesNotCompile( ); }",
    )

    assert not result.ok
    assert "ScriptAttacked" not in project.behavior_profile["script_hooks"]
    assert any(value["code"] == "script.compile_failed" for value in result.diagnostics)


def test_optional_spawn_helper_is_compiled_and_included_in_runtime_plan(tmp_path: Path) -> None:
    project = CustomRiggedCharacterProject(
        creature_name="Borhek",
        resource_name="c_borhek",
        target_game="K2",
        output_project_folder=str(tmp_path),
        appearance_settings={"donor_row": 605},
        utc_settings={"resref": "c_borhek", "display_name": "Borhek"},
    )
    project.gameplay_settings["generate_spawn_script"] = True
    spawn_resref = spawn_test_script_resref(project)
    assert spawn_resref == "spawn_c_borhek"
    assert 'CreateObject(OBJECT_TYPE_CREATURE, "c_borhek"' in spawn_test_script_source(project)

    prepared = CustomRiggedCharacterBehaviorService().prepare_build(project, None)
    assert prepared.ok, prepared.error
    resources = {(resref, restype): data for resref, restype, data in prepared.resources}
    assert resources[(spawn_resref, "nss")].startswith(b"// Ghost Studio test spawn")
    assert resources[(spawn_resref, "ncs")].startswith(b"NCS V1.0")
    assert prepared.report["test_spawn_script"]["ok"] is True

    model = tmp_path / "model"
    model.mkdir()
    (model / "c_borhek.mdl").write_bytes(b"mdl")
    (model / "c_borhek.mdx").write_bytes(b"mdx")
    package = CustomRiggedCharacterPackagingService(process_is_running=lambda _name: False).build_package(
        project,
        {"mdl": str(model / "c_borhek.mdl"), "mdx": str(model / "c_borhek.mdx")},
        tmp_path / "package",
        behavior_resources=prepared.resources,
        behavior_report=prepared.report,
    )
    assert package.ok, package.error
    additional = Path(package.package_directory) / "additional"
    assert (additional / f"{spawn_resref}.nss").is_file()
    assert (additional / f"{spawn_resref}.ncs").read_bytes().startswith(b"NCS V1.0")
    plan = json.loads((additional / "install-plan.json").read_text(encoding="utf-8"))
    assert f"{spawn_resref}.ncs" in plan["runtime_files"]
    assert not any("no compiled NCS" in warning for warning in package.warnings)


@pytest.mark.skipif(
    not Path(r"C:\Program Files (x86)\Steam\steamapps\common\Knights of the Old Republic II").is_dir(),
    reason="Installed K2 evidence is unavailable",
)
def test_installed_k2_catalog_contains_zakkeg_ground_truth() -> None:
    catalog = InstalledUtcTemplateCatalog(
        r"C:\Program Files (x86)\Steam\steamapps\common\Knights of the Old Republic II",
        game="K2",
    )
    entries = {row.resref: row for row in catalog.scan()}

    assert len(entries) >= 1000
    zakkeg = entries["c_zakkeg01"]
    assert "zakkeg" in zakkeg.display_name.casefold()
    assert zakkeg.appearance_type == 605
    assert zakkeg.faction_id == 1
    assert zakkeg.max_hit_points == 97
    assert zakkeg.script_hooks["ScriptHeartbeat"] == "k_def_heartbt01"
    assert zakkeg.script_hooks["ScriptAttacked"] == "k_def_attacked01"
    assert zakkeg.script_hooks["ScriptSpawn"] == "k_def_ambmob"
    assert entries["c_zakkeg002"].module_only_script_hooks
