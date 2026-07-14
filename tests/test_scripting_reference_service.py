from __future__ import annotations

from pykotor.common.misc import Game
from pykotor.resource.formats.ncs import bytes_ncs, compile_nss

from src.core.scripting.reference import NWScriptReferenceService, inspect_ncs
from src.core.scripting.studio import ScriptingStudioService


def test_reference_exposes_real_k1_and_k2_compiler_definitions() -> None:
    k1 = NWScriptReferenceService.functions("K1")
    k2 = NWScriptReferenceService.functions("K2")

    assert len(k1) == 772
    assert len(k2) >= len(k1)
    random = NWScriptReferenceService.function("Random", game="K2")
    assert random is not None
    assert random.routine_id == 0
    assert random.signature == "int Random(int nMaxInteger)"
    assert NWScriptReferenceService.search_functions("journal", game="K2")


def test_ncs_inspection_always_keeps_authoritative_disassembly() -> None:
    payload = bytes(bytes_ncs(compile_nss("void main() { int n = Random(4); }", Game.K1)))
    result = inspect_ncs(payload, game="K1", resref="inspect_me")

    assert result.byte_count == len(payload)
    assert result.instruction_count > 0
    assert "ACTION" in result.disassembly
    assert result.recovered_source


def test_studio_ncs_document_retains_original_fingerprint_and_disassembly() -> None:
    payload = bytes(bytes_ncs(compile_nss("void main() { int n = Random(2); }", Game.K1)))
    document, diagnostics = ScriptingStudioService().decompile_ncs(payload, game="K1", resref="roundtrip")

    assert document.disassembly
    assert len(document.decompiled_from_sha256) == 64
    assert document.origin == "decompiled_ncs"
    assert any(row.code.startswith("script.decompile_") for row in diagnostics)
