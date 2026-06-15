"""K1/K2 module-porting decision service."""

from __future__ import annotations

from dataclasses import dataclass, field

from src.core.level import KMapProject


@dataclass
class ModulePortReport:
    ok: bool = False
    source_game: str = "K1"
    target_game: str = "K2"
    unsupported: list[str] = field(default_factory=list)
    message: str = ""
    code: str = "not_ported"


class ModulePorterService:
    def record_port_decision(self, project: KMapProject, source_game: str, target_game: str) -> ModulePortReport:
        src = source_game.upper()
        dst = target_game.upper()
        project.source_game = src
        project.target_game = dst
        project.metadata.setdefault("porting", {})
        project.metadata["porting"].update({"source_game": src, "target_game": dst, "mode": "decision_recorded"})
        project.mark_dirty()
        return ModulePortReport(
            ok=True,
            source_game=src,
            target_game=dst,
            unsupported=[],
            message=f"Recorded module port target {src} to {dst}. Resource conversion runs through existing per-resource systems.",
            code="decision_recorded",
        )
