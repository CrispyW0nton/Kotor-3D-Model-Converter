"""Headless contracts and workflows for GhostStudio narrative authoring."""

from .studio import (
    DialogueDocument,
    NarrativeBuildResult,
    NarrativeResource,
    ScriptCompileResult,
    ScriptDocument,
    ScriptingStudioService,
    StudioDiagnostic,
    dialogue_node_text,
    dialogue_structure_summary,
    imported_dialogue_unknown_fields,
    normalise_script_resref,
)
from .project import (
    LEGACY_HISTORY_FILE_TYPE,
    LEGACY_HISTORY_RECOVERY_FILE_TYPE,
    LegacyNarrativeHistoryRecord,
    LegacyNarrativeHistoryStore,
)
from .dialogue_participants import (
    DialogueParticipant,
    DialogueParticipantCatalogService,
)
from .quest import (
    QuestDefinition,
    QuestDiagnostic,
    QuestScaffoldResult,
    QuestScaffoldService,
    QuestScriptResource,
    QuestStateDefinition,
    QuestStateTemplate,
    QuestTriggerDefinition,
    QuestVariableDefinition,
)

__all__ = [
    "DialogueDocument",
    "DialogueParticipant",
    "DialogueParticipantCatalogService",
    "LEGACY_HISTORY_FILE_TYPE",
    "LEGACY_HISTORY_RECOVERY_FILE_TYPE",
    "LegacyNarrativeHistoryRecord",
    "LegacyNarrativeHistoryStore",
    "NarrativeBuildResult",
    "NarrativeResource",
    "QuestDefinition",
    "QuestDiagnostic",
    "QuestScaffoldResult",
    "QuestScaffoldService",
    "QuestScriptResource",
    "QuestStateDefinition",
    "QuestStateTemplate",
    "QuestTriggerDefinition",
    "QuestVariableDefinition",
    "ScriptCompileResult",
    "ScriptDocument",
    "ScriptingStudioService",
    "StudioDiagnostic",
    "dialogue_node_text",
    "dialogue_structure_summary",
    "imported_dialogue_unknown_fields",
    "normalise_script_resref",
]
