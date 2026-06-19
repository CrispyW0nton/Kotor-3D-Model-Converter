"""Blueprint placeholder service for KMAP/GModular workflows."""

from __future__ import annotations

from src.core.level import BlueprintEntry, KMapProject, LevelScene


class ModuleBlueprintService:
    def add_blueprint(
        self,
        project: KMapProject,
        name: str,
        *,
        blueprint_type: str = "Custom",
        template_resref: str = "",
    ) -> BlueprintEntry:
        return LevelScene(project).add_blueprint(name, blueprint_type=blueprint_type, template_resref=template_resref)

    def remove_blueprint(self, project: KMapProject, blueprint_id: str) -> bool:
        before = len(project.blueprints)
        project.blueprints = [item for item in project.blueprints if item.blueprint_id != blueprint_id]
        changed = len(project.blueprints) != before
        if changed:
            project.mark_dirty()
        return changed

    def send_to_gmodular(self, _blueprint: BlueprintEntry | None = None) -> tuple[bool, str]:
        return False, "GModular bridge is not configured yet."
