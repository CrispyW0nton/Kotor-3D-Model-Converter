"""Renderer-aware integration services for Qt tools and panels."""

from .editor_services import (
    ActiveViewportService,
    DiagnosticsService,
    EditorIntegrationEventBus,
    RendererService,
    SceneService,
    SelectionService,
)
from .tool_integration_registry import (
    ToolIntegrationInfo,
    ToolIntegrationRegistry,
    build_default_tool_integration_registry,
)

__all__ = [
    "ActiveViewportService",
    "DiagnosticsService",
    "EditorIntegrationEventBus",
    "RendererService",
    "SceneService",
    "SelectionService",
    "ToolIntegrationInfo",
    "ToolIntegrationRegistry",
    "build_default_tool_integration_registry",
]
"""GhostRigger Qt integration helpers."""

from pkgutil import extend_path

__path__ = extend_path(__path__, __name__)
