"""FBX backend registry and factory.

This module keeps the Retarget Workbench's FBX backend choices explicit:

* Blender 4.2 headless is the production default.
* Autodesk FBX SDK is optional and must be verified in the active Python
  runtime before it is used.

Autodesk setup notes:

* Install Autodesk FBX SDK 2020.3.4 or later for Windows x64.
* Install Python bindings for the exact Python runtime that launches
  GhostRigger. ABI mismatches should be reported here, not discovered in UI.
* Verify with ``import fbx; fbx.FbxManager.Create()``.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from enum import Enum
import logging
from pathlib import Path
import sys
from typing import Any, Callable, Dict, Optional

from .fbx_exporter import FBXExportFailure, blender_version, find_blender_executable
from .fbx_importer import BlenderFbxBackend, import_ue_fbx_animation_clip
from .source_animation import SourceSkeletonClip


logger = logging.getLogger(__name__)


class FBXBackendType(Enum):
    """Known FBX backend families."""

    BLENDER_HEADLESS = "blender"
    AUTODESK_SDK = "autodesk_sdk"


@dataclass(frozen=True)
class BackendInfo:
    """Human-readable backend availability and setup facts."""

    name: str
    version: str
    available: bool
    sdk_used: str
    requirements_met: bool
    error_message: Optional[str] = None
    python_executable: str = sys.executable
    python_version: str = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"


class AbstractFBXImporter(ABC):
    """Unified interface for FBX animation import backends."""

    @abstractmethod
    def import_animation(self, fbx_path: Path) -> SourceSkeletonClip:
        """Import FBX animation data as a ``SourceSkeletonClip``."""

    @abstractmethod
    def is_available(self) -> bool:
        """Return whether this backend can run in the current environment."""

    @abstractmethod
    def get_backend_info(self) -> BackendInfo:
        """Return detailed backend availability information."""


class BlenderFBXImporter(AbstractFBXImporter):
    """Production default backend using headless Blender."""

    DEFAULT_EXECUTABLE_PATH = Path(r"C:\Program Files\Blender Foundation\Blender 4.2\blender.exe")
    REQUIRED_VERSION = (4, 2, 0)

    def __init__(self, blender_executable: str | Path | None = None):
        self.blender_executable = Path(blender_executable) if blender_executable else None

    def _resolve_executable(self) -> Path:
        return find_blender_executable(self.blender_executable)

    def is_available(self) -> bool:
        try:
            self._resolve_executable()
            return True
        except FBXExportFailure:
            return False

    def get_backend_info(self) -> BackendInfo:
        try:
            executable = self._resolve_executable()
        except FBXExportFailure as exc:
            return BackendInfo(
                name="Blender Headless",
                version="Not Available",
                available=False,
                sdk_used="Blender built-in FBX importer",
                requirements_met=False,
                error_message=str(exc),
            )

        try:
            version = blender_version(executable).splitlines()[0].strip()
        except Exception as exc:
            version = "Unknown"
            error_message = f"Blender found at {executable}, but version check failed: {exc}"
        else:
            error_message = None

        return BackendInfo(
            name="Blender Headless",
            version=version,
            available=True,
            sdk_used="Blender built-in FBX importer/exporter",
            requirements_met=True,
            error_message=error_message,
        )

    def import_animation(self, fbx_path: Path) -> SourceSkeletonClip:
        if not self.is_available():
            raise EnvironmentError(self.get_backend_info().error_message or "Blender backend is not available.")
        backend = None
        if self.blender_executable is not None:
            backend = BlenderFbxBackend(blender_executable=self.blender_executable)
        return import_ue_fbx_animation_clip(
            str(fbx_path),
            backend=backend,
        )


class AutodeskSDKFBXImporter(AbstractFBXImporter):
    """Optional Autodesk FBX SDK backend for verified local SDK installs."""

    def __init__(self, module_loader: Callable[[], Any] | None = None):
        self._module_loader = module_loader
        self._fbx_module: Any | None = None
        self._sdk_version: str | None = None
        self._init_error: str | None = None
        self._initialize_sdk()

    def _load_module(self) -> Any:
        if self._module_loader is not None:
            return self._module_loader()
        import fbx  # type: ignore[import-not-found]

        return fbx

    def _initialize_sdk(self) -> None:
        try:
            fbx_module = self._load_module()
            manager = fbx_module.FbxManager.Create()
            if manager:
                self._fbx_module = fbx_module
                self._sdk_version = str(manager.GetVersion())
                manager.Destroy()
            else:
                self._init_error = "Failed to create FBX Manager."
        except ImportError as exc:
            self._init_error = (
                f"FBX module import failed under {sys.executable} "
                f"(Python {sys.version_info.major}.{sys.version_info.minor}): {exc}"
            )
        except Exception as exc:
            self._init_error = f"FBX SDK initialization error: {exc}"

    def is_available(self) -> bool:
        return self._fbx_module is not None and self._init_error is None

    def get_backend_info(self) -> BackendInfo:
        if self.is_available():
            return BackendInfo(
                name="Autodesk FBX SDK",
                version=self._sdk_version or "Unknown",
                available=True,
                sdk_used="Autodesk FBX SDK Python Bindings",
                requirements_met=True,
            )
        return BackendInfo(
            name="Autodesk FBX SDK",
            version="Not Available",
            available=False,
            sdk_used="Autodesk FBX SDK Python Bindings",
            requirements_met=False,
            error_message=self._init_error or "Unknown initialization error.",
        )

    def import_animation(self, fbx_path: Path) -> SourceSkeletonClip:
        if not self.is_available():
            raise RuntimeError(
                f"Autodesk FBX SDK not available: {self._init_error}. "
                "See BACKEND_REGISTRY.md for installation instructions."
            )
        raise NotImplementedError(
            "AutodeskSDKFBXImporter.import_animation() is pending implementation. "
            "The SDK probe is available so the machine setup can be verified first."
        )


class FBXBackendFactory:
    """Create FBX importers with explicit backend behavior."""

    @staticmethod
    def backend_type_from_string(value: str | None) -> FBXBackendType:
        text = str(value or "").strip().lower()
        if text in {"autodesk", "autodesk_sdk", "sdk", "fbx_sdk"}:
            return FBXBackendType.AUTODESK_SDK
        return FBXBackendType.BLENDER_HEADLESS

    @staticmethod
    def get_importer(
        preferred: FBXBackendType = FBXBackendType.BLENDER_HEADLESS,
        *,
        allow_fallback: bool = False,
    ) -> AbstractFBXImporter:
        """Return the requested backend.

        Blender and Autodesk SDK imports are separate options.  Autodesk SDK
        requests fail clearly by default when the SDK is unavailable; callers
        must opt in to Blender fallback for legacy compatibility.
        """

        if preferred == FBXBackendType.AUTODESK_SDK:
            sdk_importer = AutodeskSDKFBXImporter()
            if sdk_importer.is_available():
                logger.info("Using Autodesk FBX SDK backend")
                return sdk_importer
            if not allow_fallback:
                raise EnvironmentError(sdk_importer.get_backend_info().error_message)
            logger.warning(
                "Autodesk SDK requested but not available: %s. Falling back to Blender backend.",
                sdk_importer.get_backend_info().error_message,
            )

        blender_importer = BlenderFBXImporter()
        if blender_importer.is_available():
            logger.info("Using Blender headless FBX backend")
            return blender_importer
        raise EnvironmentError(
            "No FBX backends available. Check BACKEND_REGISTRY.md for setup instructions."
        )

    @staticmethod
    def get_importer_from_environment(*, allow_fallback: bool = False) -> AbstractFBXImporter:
        import os

        return FBXBackendFactory.get_importer(
            FBXBackendFactory.backend_type_from_string(os.environ.get("FBX_BACKEND")),
            allow_fallback=allow_fallback,
        )

    @staticmethod
    def list_available_backends() -> Dict[FBXBackendType, BackendInfo]:
        """Return availability information for all known backends."""

        blender = BlenderFBXImporter()
        autodesk = AutodeskSDKFBXImporter()
        return {
            FBXBackendType.BLENDER_HEADLESS: blender.get_backend_info(),
            FBXBackendType.AUTODESK_SDK: autodesk.get_backend_info(),
        }
