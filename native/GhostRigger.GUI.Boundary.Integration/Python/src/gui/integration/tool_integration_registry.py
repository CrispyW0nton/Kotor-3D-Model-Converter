"""Diagnostic registry for renderer-aware tool and panel integration."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class ToolIntegrationInfo:
    tool_id: str
    menu_name: str
    class_name: str
    opens_from: str
    depends_on_viewport: bool = False
    depends_on_renderer: bool = False
    depends_on_selection: bool = False
    depends_on_camera: bool = False
    depends_on_scene: bool = False
    depends_on_animation: bool = False
    supported_renderers: tuple[str, ...] = ("modern_gl", "wgpu_auto", "wgpu_d3d12", "wgpu_vulkan", "wgpu_opengl")
    requires_modern_gl: bool = False
    wgpu_supported: bool = True
    null_supported: bool = False
    known_limitations: str = ""
    touches_mesh_material_texture: bool = False
    touches_bones_animation: bool = False
    assumes_qopengl: bool = False
    assumes_qlabel_pil: bool = False
    integration_notes: str = ""


@dataclass
class ToolIntegrationRegistry:
    tools: dict[str, ToolIntegrationInfo] = field(default_factory=dict)

    def register(self, info: ToolIntegrationInfo) -> None:
        self.tools[info.tool_id] = info

    def get(self, tool_id: str) -> ToolIntegrationInfo | None:
        return self.tools.get(tool_id)

    def all_tools(self) -> list[ToolIntegrationInfo]:
        return [self.tools[key] for key in sorted(self.tools)]

    def compatibility_rows(self) -> list[dict[str, object]]:
        return [
            {
                "tool_id": info.tool_id,
                "menu_name": info.menu_name,
                "class_name": info.class_name,
                "opens_from": info.opens_from,
                "supported_renderers": ", ".join(info.supported_renderers),
                "requires_modern_gl": info.requires_modern_gl,
                "wgpu_supported": info.wgpu_supported,
                "null_supported": info.null_supported,
                "known_limitations": info.known_limitations,
            }
            for info in self.all_tools()
        ]


def build_default_tool_integration_registry() -> ToolIntegrationRegistry:
    registry = ToolIntegrationRegistry()
    for info in _DEFAULT_TOOLS:
        registry.register(info)
    return registry


_ALL_RENDERERS = ("modern_gl", "wgpu_auto", "wgpu_d3d12", "wgpu_vulkan", "wgpu_opengl", "null_diagnostic")
_LIVE_RENDERERS = ("modern_gl", "wgpu_auto", "wgpu_d3d12", "wgpu_vulkan", "wgpu_opengl")


_DEFAULT_TOOLS = (
    ToolIntegrationInfo(
        "module_editor",
        "Open Map Studio Level Editor",
        "ModuleEditorWindow",
        "Modules menu",
        depends_on_viewport=True,
        depends_on_scene=True,
        touches_mesh_material_texture=True,
        supported_renderers=_LIVE_RENDERERS,
        null_supported=True,
        known_limitations="Null Diagnostic opens editor panels but does not render a live module scene.",
        integration_notes="Module Editor icon opens the existing Level Editor as Map Studio; main shell resource loads route through content browser services.",
    ),
    ToolIntegrationInfo(
        "rigging_window",
        "Open Rigging Window",
        "QtRigWindow",
        "Modules menu",
        depends_on_viewport=True,
        depends_on_selection=True,
        touches_bones_animation=True,
        supported_renderers=_LIVE_RENDERERS,
        null_supported=True,
        known_limitations="Null Diagnostic can edit panel state but has no skeleton overlay rendering.",
    ),
    ToolIntegrationInfo(
        "retarget_workbench",
        "Animation Retargeting Workbench",
        "QtAnimationRetargetWindow",
        "Modules/Retarget menus",
        depends_on_viewport=True,
        depends_on_animation=True,
        touches_bones_animation=True,
        supported_renderers=_LIVE_RENDERERS,
        null_supported=True,
        known_limitations="Retarget algorithms remain headless; live preview requires a rendering backend.",
    ),
    ToolIntegrationInfo(
        "unreal_animator",
        "Unreal Animator...",
        "QtUnrealAnimatorWindow",
        "Modules/Retarget menus",
        depends_on_viewport=True,
        depends_on_renderer=True,
        depends_on_animation=True,
        touches_bones_animation=True,
        supported_renderers=_LIVE_RENDERERS,
        null_supported=False,
        known_limitations="Split preview viewports use shared GPU renderer settings; Null Diagnostic is diagnostic-only.",
    ),
    ToolIntegrationInfo(
        "sequence_editor_dock",
        "Sequence Editor",
        "SequenceEditorWindow",
        "Modules menu / command strip",
        depends_on_viewport=True,
        depends_on_camera=True,
        depends_on_scene=True,
        depends_on_animation=True,
        supported_renderers=_LIVE_RENDERERS,
        null_supported=True,
        known_limitations="Offline frame render still uses viewport frame renderer.",
    ),
    ToolIntegrationInfo(
        "sequence_editor_window",
        "Sequence Editor (Window)...",
        "SequenceEditorWindow",
        "Modules menu",
        depends_on_viewport=True,
        depends_on_camera=True,
        depends_on_scene=True,
        depends_on_animation=True,
        supported_renderers=_LIVE_RENDERERS,
        null_supported=True,
        known_limitations="Detached window keeps source viewport reference; no independent render loop is created.",
    ),
    ToolIntegrationInfo(
        "content_browser",
        "Open Content Browser",
        "QtContentBrowserPanel",
        "Modules menu / command strip",
        depends_on_scene=True,
        touches_mesh_material_texture=True,
        supported_renderers=_ALL_RENDERERS,
        wgpu_supported=True,
        null_supported=True,
        known_limitations="Browser is data-first; renderer only participates when opening or previewing assets.",
    ),
    ToolIntegrationInfo("scene_information", "Scene Information", "QtSceneOutlinerPanel", "Modules menu / dock", depends_on_scene=True, depends_on_selection=True, supported_renderers=_ALL_RENDERERS, null_supported=True),
    ToolIntegrationInfo("properties", "Open Properties", "QtPropertiesPanel", "Modules menu / dock", depends_on_selection=True, depends_on_scene=True, touches_mesh_material_texture=True, supported_renderers=_ALL_RENDERERS, null_supported=True),
    ToolIntegrationInfo("nodes", "Open Nodes Panel", "QtSkeletonPanel", "Modules menu / dock", depends_on_selection=True, depends_on_scene=True, touches_bones_animation=True, supported_renderers=_ALL_RENDERERS, null_supported=True),
    ToolIntegrationInfo("lighting", "Open Lighting Panel", "QtLightingPanel", "Modules menu / dock", depends_on_viewport=True, depends_on_renderer=True, depends_on_scene=True, supported_renderers=_LIVE_RENDERERS, null_supported=True, known_limitations="Advanced lighting remains ModernGL-first; WGPU receives neutral lighting/display flags where supported."),
    ToolIntegrationInfo("camera", "Open Camera Panel", "QtCameraPanel", "Modules menu / dock", depends_on_viewport=True, depends_on_camera=True, supported_renderers=_ALL_RENDERERS, null_supported=True),
    ToolIntegrationInfo("module_meshes", "Open Module Meshes", "QtPropertiesPanel(module browser)", "Modules menu / dock", depends_on_viewport=True, depends_on_selection=True, touches_mesh_material_texture=True, supported_renderers=_LIVE_RENDERERS, null_supported=True, known_limitations="Null Diagnostic updates selection/visibility state but does not draw mesh highlights."),
    ToolIntegrationInfo("adjust_pivot", "Open Adjust Pivot", "AdjustPivotPanel", "Modules menu / dock", depends_on_viewport=True, depends_on_selection=True, depends_on_scene=True, supported_renderers=_ALL_RENDERERS, null_supported=True),
    ToolIntegrationInfo("twoda_browser", "Open 2DA Browser", "QtTwoDaBrowserPanel", "Modules menu / dock", supported_renderers=_ALL_RENDERERS, null_supported=True, known_limitations="Data editor only unless a resource preview is launched."),
    ToolIntegrationInfo("resource_browser", "Open Resource Browser", "QtResourceBrowserPanel", "Modules menu / dock", depends_on_scene=True, touches_mesh_material_texture=True, supported_renderers=_ALL_RENDERERS, null_supported=True),
    ToolIntegrationInfo("diagnostics", "Diagnostics...", "QtDiagnosticsPanel", "Tools/Help menus", depends_on_viewport=True, depends_on_renderer=True, depends_on_scene=True, supported_renderers=_ALL_RENDERERS, null_supported=True),
    ToolIntegrationInfo("texture_tool", "Texture Tool...", "QtTextureToolWindow", "Tools menu", touches_mesh_material_texture=True, supported_renderers=_ALL_RENDERERS, null_supported=True),
    ToolIntegrationInfo("blueprint_editor", "Blueprint Editor...", "QtBlueprintEditorWindow", "Tools menu", supported_renderers=_ALL_RENDERERS, null_supported=True),
    ToolIntegrationInfo("character_builder", "Character Builder (New Window)...", "QtCharacterBuilderWindow", "Tools menu", depends_on_viewport=True, depends_on_selection=True, touches_bones_animation=True, supported_renderers=_LIVE_RENDERERS, null_supported=True),
    ToolIntegrationInfo("render_camera_still", "Render Camera Still...", "QtRenderFrameDialog", "Tools menu", depends_on_viewport=True, depends_on_renderer=True, depends_on_camera=True, supported_renderers=_LIVE_RENDERERS, null_supported=False),
    ToolIntegrationInfo("mesh_tools", "Mesh Tools dock", "QtMeshToolsPanel", "dock widget", depends_on_viewport=True, depends_on_selection=True, touches_mesh_material_texture=True, supported_renderers=_LIVE_RENDERERS, null_supported=True),
    ToolIntegrationInfo("viewport_toolbar", "Viewport toolbar/tools", "QtMainViewportWidget toolbar", "main toolbar", depends_on_viewport=True, depends_on_renderer=True, depends_on_selection=True, depends_on_camera=True, supported_renderers=_ALL_RENDERERS, null_supported=True, known_limitations="Unsupported display modes are gated by renderer capabilities and fallbacks."),
    ToolIntegrationInfo("ipc_menu", "IPC menu", "src.ipc.client/server", "IPC menu", depends_on_scene=True, supported_renderers=_ALL_RENDERERS, null_supported=True, known_limitations="Current IPC menu actions ping/notify external tools; viewport-affecting IPC should route through services."),
)
