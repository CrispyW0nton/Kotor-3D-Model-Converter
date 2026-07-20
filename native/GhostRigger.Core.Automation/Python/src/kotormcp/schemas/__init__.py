"""Pydantic v2 input models for MCP tool arguments.

Falls back gracefully if pydantic is not installed (uses a simple dict-based shim).
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

try:
    from pydantic import BaseModel, Field
    _PYDANTIC = True
except ImportError:
    _PYDANTIC = False

    class BaseModel:  # type: ignore[no-redef]
        """Minimal shim when pydantic is not installed."""
        def __init__(self, **kwargs: Any):
            for k, v in kwargs.items():
                setattr(self, k, v)

        @classmethod
        def model_validate(cls, data: Dict[str, Any]):
            instance = cls.__new__(cls)
            for k, v in data.items():
                setattr(instance, k, v)
            # Set defaults from annotations
            for attr, annotation in cls.__annotations__.items():
                if not hasattr(instance, attr):
                    setattr(instance, attr, None)
            return instance

    def Field(default=None, **kwargs):  # type: ignore[misc]
        return default


# ── Input models ──────────────────────────────────────────────────────────────

class LoadInstallationInput(BaseModel):
    game: str = Field(..., description="Game alias: k1, k2, or tsl")
    path: Optional[str] = Field(None, description="Optional absolute path to installation")


class ListResourcesInput(BaseModel):
    game: str = Field(..., description="Game alias: k1 or k2")
    location: str = Field(default="all")
    moduleFilter: Optional[str] = Field(None)  # noqa: N815
    resourceTypes: Optional[List[str]] = Field(None)  # noqa: N815
    resrefQuery: Optional[str] = Field(None)  # noqa: N815
    limit: int = Field(default=50)
    offset: int = Field(default=0)


class DescribeResourceInput(BaseModel):
    game: str = Field(..., description="Game alias: k1 or k2")
    resref: str = Field(...)
    restype: str = Field(...)
    order: Optional[List[str]] = Field(None)


class JournalOverviewInput(BaseModel):
    game: str = Field(...)


class Lookup2daInput(BaseModel):
    game: str = Field(...)
    table_name: str = Field(...)
    row_index: Optional[int] = Field(None)
    column: Optional[str] = Field(None)
    value_search: Optional[str] = Field(None)


class LookupTlkInput(BaseModel):
    game: str = Field(...)
    strref: int = Field(...)


class FindResourceInput(BaseModel):
    game: str = Field(...)
    query: str = Field(...)
    order: Optional[List[str]] = Field(None)
    all_locations: bool = Field(default=True)


class SearchResourcesInput(BaseModel):
    game: str = Field(...)
    pattern: str = Field(...)
    location: str = Field(default="all")
    limit: int = Field(default=50)
    offset: int = Field(default=0)


class ListModulesInput(BaseModel):
    game: str = Field(...)


class DescribeModuleInput(BaseModel):
    game: str = Field(...)
    module_root: str = Field(...)


class ModuleResourcesInput(BaseModel):
    game: str = Field(...)
    module_root: str = Field(...)
    limit: int = Field(default=50)
    offset: int = Field(default=0)


class ListSavesInput(BaseModel):
    game: str = Field(..., description="Game alias: k1, k2, or tsl")
    path: Optional[str] = Field(None, description="Optional absolute path to installation")
    save_root: Optional[str] = Field(None, description="Optional folder containing save directories")
    limit: int = Field(default=25)
    offset: int = Field(default=0)


class PrepareSaveWarpTestInput(BaseModel):
    game: str = Field(..., description="Game alias: k1, k2, or tsl")
    path: Optional[str] = Field(None, description="Optional absolute path to installation")
    target_module: str = Field(default="tst_light")
    save_folder: Optional[str] = Field(None, description="Optional exact save folder path")
    save_name: Optional[str] = Field(None, description="Optional save name or folder-name substring to prefer")
    save_root: Optional[str] = Field(None, description="Optional folder containing save directories")
    require_loaded_save_before_warp: bool = Field(default=True)
    require_dinput_hook: bool = Field(default=False)
    launch_game: bool = Field(default=False)
    steam_app_id: Optional[int] = Field(None)


class KotorInputStatusInput(BaseModel):
    game: str = Field(default="k2", description="Game alias: k1, k2, or tsl")
    window_title: Optional[str] = Field(None, description="Optional exact/partial window title")


class KotorInputClickInput(BaseModel):
    game: str = Field(default="k2", description="Game alias: k1, k2, or tsl")
    path: Optional[str] = Field(None, description="Optional absolute path to installation")
    window_title: Optional[str] = Field(None, description="Optional exact/partial window title")
    use_dinput_hook: bool = Field(default=False)
    x: float = Field(...)
    y: float = Field(...)
    coordinate_space: str = Field(default="ratio")
    clicks: int = Field(default=1)
    delay_seconds: float = Field(default=0.5)


class KotorInputTypeInput(BaseModel):
    game: str = Field(default="k2", description="Game alias: k1, k2, or tsl")
    path: Optional[str] = Field(None, description="Optional absolute path to installation")
    window_title: Optional[str] = Field(None, description="Optional exact/partial window title")
    use_dinput_hook: bool = Field(default=False)
    text: str = Field(...)
    open_console: bool = Field(default=False)
    press_enter: bool = Field(default=False)
    key_delay_seconds: float = Field(default=0.035)


class KotorCaptureWindowInput(BaseModel):
    game: str = Field(default="k2", description="Game alias: k1, k2, or tsl")
    window_title: Optional[str] = Field(None, description="Optional exact/partial window title")
    output_path: str = Field(...)
    region: str = Field(default="client")
    activate: bool = Field(default=True)
    clip_to_work_area: bool = Field(default=True)
    settle_seconds: float = Field(default=0.25)


class KotorRunSaveWarpRouteInput(BaseModel):
    game: str = Field(default="k2", description="Game alias: k1, k2, or tsl")
    path: Optional[str] = Field(None, description="Optional absolute path to installation")
    window_title: Optional[str] = Field(None, description="Optional exact/partial window title")
    use_dinput_hook: bool = Field(default=False)
    target_module: str = Field(default="tst_light")
    start_screen: str = Field(default="main_menu")
    save_row_index: int = Field(default=1)
    main_menu_load_x_ratio: float = Field(default=0.604)
    main_menu_load_y_ratio: float = Field(default=0.547)
    save_row_x_ratio: float = Field(default=0.302)
    save_row_first_y_ratio: float = Field(default=0.266)
    save_row_step_ratio: float = Field(default=0.039)
    load_button_x_ratio: float = Field(default=0.334)
    load_button_y_ratio: float = Field(default=0.882)
    after_menu_seconds: float = Field(default=2.0)
    after_load_seconds: float = Field(default=12.0)
    after_warp_seconds: float = Field(default=15.0)


class KotorLogStartInput(BaseModel):
    game: str = Field(default="k2", description="Game alias: k1, k2, or tsl")
    path: Optional[str] = Field(None, description="Optional absolute installation path")
    session_label: Optional[str] = Field(default="kotor-live")
    pid: Optional[int] = Field(None)
    wait_for_process: bool = Field(default=True)
    duration_seconds: int = Field(default=900)
    asset_resrefs: Optional[List[str]] = Field(default=None)
    session_root: Optional[str] = Field(None)
    expected_warp_target: Optional[str] = Field(
        None,
        description="Optional module resref expected to be entered with the warp console command",
    )
    expected_module_sha256: Optional[str] = Field(
        None,
        description="Optional required SHA-256 for Modules/<expected_warp_target>.mod",
    )


class KotorLogStatusInput(BaseModel):
    session_dir: Optional[str] = Field(None)
    session_root: Optional[str] = Field(None)


class KotorLogStopInput(BaseModel):
    session_dir: Optional[str] = Field(None)
    session_root: Optional[str] = Field(None)


class KotorLogAnalyzeInput(BaseModel):
    game: str = Field(default="k2", description="Game alias: k1, k2, or tsl")
    session_dir: Optional[str] = Field(None)
    session_root: Optional[str] = Field(None)
    annotate_with_ghidra: bool = Field(default=True)
    ghidra_program: Optional[str] = Field(None)


class KotorDInputHookStatusInput(BaseModel):
    game: str = Field(default="k2", description="Game alias: k1, k2, or tsl")
    path: Optional[str] = Field(None, description="Optional absolute path to installation")
    proxy_path: Optional[str] = Field(None, description="Optional built dinput8.dll path")


class KotorDInputHookInstallInput(BaseModel):
    game: str = Field(default="k2", description="Game alias: k1, k2, or tsl")
    path: Optional[str] = Field(None, description="Optional absolute path to installation")
    proxy_path: Optional[str] = Field(None, description="Optional built dinput8.dll path")
    backup_root: Optional[str] = Field(None, description="Optional backup output root")
    force: bool = Field(default=False)
    dry_run: bool = Field(default=False)


class KotorDInputHookSendInput(BaseModel):
    game: str = Field(default="k2", description="Game alias: k1, k2, or tsl")
    path: Optional[str] = Field(None, description="Optional absolute path to installation")
    proxy_path: Optional[str] = Field(None, description="Optional built dinput8.dll path")
    commands: Optional[List[str]] = Field(default=None)
    text: Optional[str] = Field(default=None)
    open_console: bool = Field(default=False)
    press_enter: bool = Field(default=False)
    mouse_click: bool = Field(default=False)
    reset_first: bool = Field(default=False)
    key_polls: int = Field(default=12)
    mouse_polls: int = Field(default=24)


class ListArchiveInput(BaseModel):
    file_path: str = Field(...)
    key_file: Optional[str] = Field(None)
    limit: int = Field(default=50)
    offset: int = Field(default=0)


class ExtractResourceInput(BaseModel):
    game: str = Field(...)
    resref: str = Field(...)
    restype: str = Field(...)
    output_path: str = Field(...)
    source: Optional[str] = Field(None)


class ReadGffInput(BaseModel):
    game: str = Field(...)
    resref: str = Field(...)
    restype: str = Field(...)
    field_paths: Optional[List[str]] = Field(None)
    max_depth: Optional[int] = Field(None)
    max_fields: Optional[int] = Field(None)


class Read2daInput(BaseModel):
    game: str = Field(...)
    resref: str = Field(...)
    row_start: Optional[int] = Field(None)
    row_end: Optional[int] = Field(None)
    columns: Optional[List[str]] = Field(None)


class ReadTlkInput(BaseModel):
    game: str = Field(...)
    strref_start: Optional[int] = Field(None)
    strref_end: Optional[int] = Field(None)
    text_search: Optional[str] = Field(None)
    limit: int = Field(default=100)


class ListReferencesInput(BaseModel):
    game: str = Field(...)
    resref: str = Field(...)
    restype: str = Field(...)
    path: Optional[str] = Field(None)


class FindReferrersInput(BaseModel):
    game: str = Field(...)
    value: str = Field(...)
    reference_kind: str = Field(default="resref")
    path: Optional[str] = Field(None)
    module_root: Optional[str] = Field(None)
    partial_match: bool = Field(default=False)
    case_sensitive: bool = Field(default=False)
    limit: int = Field(default=100)
    offset: int = Field(default=0)


class FindStrrefReferrersInput(BaseModel):
    game: str = Field(...)
    strref: int = Field(...)
    path: Optional[str] = Field(None)
    limit: int = Field(default=100)
    offset: int = Field(default=0)


class DescribeDlgInput(BaseModel):
    game: str = Field(...)
    resref: str = Field(...)
    path: Optional[str] = Field(None)


class DescribeJrlInput(BaseModel):
    game: str = Field(...)
    resref: str = Field(...)
    path: Optional[str] = Field(None)


class DescribeResourceRefsInput(BaseModel):
    game: str = Field(...)
    resref: str = Field(...)
    restype: str = Field(...)
    path: Optional[str] = Field(None)
