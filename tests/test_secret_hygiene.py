"""Repository hygiene checks for local-only tool credentials."""

from __future__ import annotations

import subprocess
from pathlib import Path


FORBIDDEN_TRACKED_SUBSTRINGS = (
    "170." "9." "241." "140",
    "http://" + "170." "9." "241." "140" + ":8080/mcp/",
    "revan" "lives",
    '"X-Agent-Server-' "Password" '":',
)


def test_tracked_files_do_not_expose_local_ghidra_endpoint_or_passwords() -> None:
    root = Path(__file__).resolve().parents[1]
    tracked = subprocess.run(
        ["git", "ls-files"],
        cwd=root,
        check=True,
        text=True,
        capture_output=True,
    ).stdout.splitlines()

    offenders: list[str] = []
    for rel in tracked:
        path = root / rel
        if not path.is_file():
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        for forbidden in FORBIDDEN_TRACKED_SUBSTRINGS:
            if forbidden in text:
                offenders.append(f"{rel}: contains {forbidden!r}")

    assert not offenders, "Local Ghidra/AgentDecompile secrets leaked into tracked files:\n" + "\n".join(offenders)
