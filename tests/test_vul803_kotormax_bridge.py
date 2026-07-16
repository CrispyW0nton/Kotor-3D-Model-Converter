from __future__ import annotations

from argparse import Namespace
from pathlib import Path
import subprocess

import scripts.recover_vul803_max_scenes as recovery
from scripts.recover_vul803_max_scenes import (
    EXPECTED_EXPORTS,
    _validate_exported_ascii,
    discover_3dsmax_batch,
)


ROOT = Path(__file__).resolve().parents[1]
KOTORMAX_BATCH = ROOT / "scripts" / "max2021_mcp" / "kotormax_batch_export.ms"
KOTORMAX_MANUAL = ROOT / "scripts" / "kotormax" / "vul803_recovery_bridge.ms"
NWMAX_MANUAL = ROOT / "scripts" / "kotormax" / "vul803_nwmax_recovery_bridge.ms"
NWMAX_LOADER = ROOT / "scripts" / "kotormax" / "vul803_nwmax_loader.ms"


def _maxscript_code(path: Path) -> str:
    text = path.read_text(encoding="utf-8")
    output: list[str] = []
    index = 0
    in_string = False
    in_block_comment = False
    while index < len(text):
        current = text[index]
        following = text[index + 1] if index + 1 < len(text) else ""
        if in_block_comment:
            if current == "*" and following == "/":
                in_block_comment = False
                index += 2
            else:
                index += 1
            continue
        if not in_string and current == "/" and following == "*":
            in_block_comment = True
            index += 2
            continue
        if not in_string and current == "-" and following == "-":
            newline = text.find("\n", index + 2)
            index = len(text) if newline < 0 else newline
            continue
        if current == '"':
            slash_count = 0
            cursor = index - 1
            while cursor >= 0 and text[cursor] == "\\":
                slash_count += 1
                cursor -= 1
            escaped = slash_count % 2 == 1
            if not escaped:
                in_string = not in_string
            output.append(" ")
            index += 1
            continue
        output.append(" " if in_string else current)
        index += 1
    assert not in_string, f"unterminated string in {path}"
    assert not in_block_comment, f"unterminated block comment in {path}"
    return "".join(output)


def _assert_balanced_maxscript(path: Path) -> None:
    code = _maxscript_code(path)
    stack: list[tuple[str, int]] = []
    pairs = {")": "(", "]": "["}
    for index, token in enumerate(code):
        if token in "([":
            stack.append((token, index))
        elif token in pairs:
            assert stack and stack[-1][0] == pairs[token], (
                f"unbalanced {token!r} at offset {index} in {path}"
            )
            stack.pop()
    assert not stack, f"unclosed delimiters in {path}: {stack[-3:]}"


def test_vul803_maxscripts_are_statically_balanced_and_never_save_scenes() -> None:
    for path in (KOTORMAX_BATCH, KOTORMAX_MANUAL, NWMAX_MANUAL, NWMAX_LOADER):
        assert path.is_file()
        _assert_balanced_maxscript(path)
        code = _maxscript_code(path).lower()
        assert "savemaxfile" not in code
        assert "loadmaxfile" not in code
        assert "mergemaxfile" not in code


def test_kotormax_batch_preserves_recovery_contracts() -> None:
    source = KOTORMAX_BATCH.read_text(encoding="utf-8")
    assert "local exportName = toLower(modelBase.name)" in source
    assert "g_exportwok = 0" in source
    assert "g_expLower = 1" in source
    assert "g_lowercase" not in source
    assert "modelBase.copy_tga = 0" in source
    assert "modelBase.tga2dds = 0" in source
    assert "ghostStudioRestoreFrozen frozenStates" in source
    assert "with animate off" in source
    assert "at time 0 node.transform = worldTM" in source
    assert "matches.count != expectedCount" in source
    assert "ghostStudioFileLength mdlPath == 0" in source


def test_legacy_nwmax_bridge_requires_exact_toolset_and_restores_scene_state() -> None:
    source = NWMAX_MANUAL.read_text(encoding="utf-8")
    assert 'gblVersion != "0.8 b60"' in source
    assert "ghostVul803NwmaxRestoreFrozen frozenStates" in source
    assert "with animate off" in source
    assert "matches.count != expectedCount" in source
    assert "replaceExistingRoot:false" in source
    loader = NWMAX_LOADER.read_text(encoding="utf-8")
    assert "KOTORMax is already loaded" in loader
    assert "ghostVul803LegacyNwmaxCoreIsReady" in loader


def test_runner_requires_all_forensic_exports_and_rejects_fake_executable(tmp_path: Path) -> None:
    assert EXPECTED_EXPORTS["lavatemple023"] == (
        "vul803_01a",
        "vul803_01c",
        "vul803_01d",
    )
    assert EXPECTED_EXPORTS["lavatemple024"] == ("vul803_01b",)
    assert EXPECTED_EXPORTS["lavatemple025sky"] == ("vul803_01e",)
    fake = tmp_path / "not-3dsmax.exe"
    fake.write_bytes(b"not a 3ds Max executable")
    assert discover_3dsmax_batch(str(fake)) is None


def test_ascii_export_validation_requires_complete_exact_model(tmp_path: Path) -> None:
    candidate = tmp_path / "vul803_01a.mdl.ascii"
    candidate.write_text(
        "newmodel vul803_01a\n"
        "beginmodelgeom vul803_01a\n"
        "endmodelgeom vul803_01a\n"
        "donemodel vul803_01a\n",
        encoding="latin-1",
    )
    assert _validate_exported_ascii(candidate, "vul803_01a") is None
    candidate.write_text("newmodel wrong\n", encoding="latin-1")
    assert _validate_exported_ascii(candidate, "vul803_01a") is not None


def test_runner_uses_fresh_evidence_dirs_and_cannot_accept_stale_exports(
    tmp_path: Path,
    monkeypatch,
) -> None:
    max_batch = tmp_path / "3dsmaxbatch.exe"
    max_batch.write_bytes(b"test executable placeholder")
    kotormax = tmp_path / "kotormax"
    kotormax.mkdir()
    scenes: list[Path] = []
    for stem in ("LavaTemple023", "LavaTemple024", "LavaTemple025Sky"):
        scene = tmp_path / f"{stem}.max"
        scene.write_bytes((stem + " source").encode("ascii"))
        scenes.append(scene)

    monkeypatch.setattr(recovery, "install_kotormax", lambda *_args: None)
    monkeypatch.setattr(recovery, "_kotormax_revision", lambda _root: "test-revision")

    def successful_batch(command, *, env, **_kwargs):
        scene = Path(command[command.index("-sceneFile") + 1])
        output = Path(env["GHOSTSTUDIO_KOTOR_EXPORT_DIR"])
        for resref in EXPECTED_EXPORTS[scene.stem.lower()]:
            (output / f"{resref}.mdl.ascii").write_text(
                f"newmodel {resref}\n"
                f"beginmodelgeom {resref}\n"
                f"endmodelgeom {resref}\n"
                f"donemodel {resref}\n",
                encoding="latin-1",
            )
        (output / "ghoststudio-kotormax-export.tsv").write_text(
            "scene\troot\n",
            encoding="utf-8",
        )
        return subprocess.CompletedProcess(command, 0, "ok", "")

    monkeypatch.setattr(recovery.subprocess, "run", successful_batch)
    args = Namespace(
        output=str(tmp_path / "output"),
        kotormax=str(kotormax),
        max_batch=str(max_batch),
        max_scripts_dir=str(tmp_path / "max-scripts"),
        scene=[str(scene) for scene in scenes],
        preflight=False,
        timeout=10.0,
    )
    first = recovery.run(args)
    assert first.ok
    assert first.code == "forensic_ascii_candidates_ready"
    assert first.original_scenes_untouched

    def no_op_batch(command, **_kwargs):
        return subprocess.CompletedProcess(command, 0, "no output", "")

    monkeypatch.setattr(recovery.subprocess, "run", no_op_batch)
    second = recovery.run(args)
    assert not second.ok
    assert second.code == "max_export_failed"
    assert first.run_id != second.run_id
    assert {item.output_dir for item in first.scene_exports}.isdisjoint(
        {item.output_dir for item in second.scene_exports}
    )
    assert all(item.missing_resrefs for item in second.scene_exports)
