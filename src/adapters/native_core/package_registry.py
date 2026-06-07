"""Thin native package availability checks for Phase 1 C++ integration."""

from __future__ import annotations

import ctypes
import json
import os
import platform
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


_NATIVE_CORE_DLL = "GhostRigger.Native.NativeCore.dll"


@dataclass(frozen=True)
class NativePackageStatus:
    name: str
    available: bool
    version: str = ""
    capabilities: dict[str, object] | None = None
    path: str = ""
    reason: str = ""


@dataclass(frozen=True)
class NativePackageSpec:
    name: str
    dll_name: str
    env_var: str = ""
    version_export: str = ""
    capabilities_export: str = ""
    windows_only: bool = True


NATIVE_CORE_PACKAGE = NativePackageSpec(
    name="GhostRigger.Native.NativeCore",
    dll_name=_NATIVE_CORE_DLL,
    env_var="GHOSTRIGGER_NATIVE_CORE",
    version_export="gr_native_core_version",
    capabilities_export="gr_native_core_capabilities_json",
)

RUNTIME_SHARED_CONTRACTS_PACKAGE = NativePackageSpec(
    name="GhostRigger.Runtime.Shared.Contracts",
    dll_name="GhostRigger.Runtime.Shared.Contracts.dll",
    env_var="GHOSTRIGGER_RUNTIME_SHARED_CONTRACTS",
    version_export="gr_runtime_shared_contracts_version",
    capabilities_export="gr_runtime_shared_contracts_capabilities_json",
)

RUNTIME_SHARED_DESCRIPTORS_PACKAGE = NativePackageSpec(
    name="GhostRigger.Runtime.Shared.Descriptors",
    dll_name="GhostRigger.Runtime.Shared.Descriptors.dll",
    env_var="GHOSTRIGGER_RUNTIME_SHARED_DESCRIPTORS",
    version_export="gr_runtime_shared_descriptors_version",
    capabilities_export="gr_runtime_shared_descriptors_capabilities_json",
)

RUNTIME_SHARED_RESOURCES_PACKAGE = NativePackageSpec(
    name="GhostRigger.Runtime.Shared.Resources",
    dll_name="GhostRigger.Runtime.Shared.Resources.dll",
    env_var="GHOSTRIGGER_RUNTIME_SHARED_RESOURCES",
    version_export="gr_runtime_shared_resources_version",
    capabilities_export="gr_runtime_shared_resources_capabilities_json",
)

RENDERER_CONTRACTS_PACKAGE = NativePackageSpec(
    name="GhostRigger.Renderer.Contracts",
    dll_name="GhostRigger.Renderer.Contracts.dll",
    env_var="GHOSTRIGGER_RENDERER_CONTRACTS",
    version_export="gr_renderer_contracts_version",
    capabilities_export="gr_renderer_contracts_capabilities_json",
)

RENDERER_NULL_PACKAGE = NativePackageSpec(
    name="GhostRigger.Renderer.Null",
    dll_name="GhostRigger.Renderer.Null.dll",
    env_var="GHOSTRIGGER_RENDERER_NULL",
    version_export="gr_renderer_null_version",
    capabilities_export="gr_renderer_null_capabilities_json",
)

NATIVE_CORE_DIAGNOSTICS_PACKAGE = NativePackageSpec(
    name="GhostRigger.Native.NativeCore.Diagnostics",
    dll_name="GhostRigger.Native.NativeCore.Diagnostics.dll",
    env_var="GHOSTRIGGER_NATIVE_CORE_DIAGNOSTICS",
    version_export="gr_native_core_diagnostics_version",
    capabilities_export="gr_native_core_diagnostics_capabilities_json",
)

NATIVE_CORE_MATH_PACKAGE = NativePackageSpec(
    name="GhostRigger.Native.NativeCore.Math",
    dll_name="GhostRigger.Native.NativeCore.Math.dll",
    env_var="GHOSTRIGGER_NATIVE_CORE_MATH",
    version_export="gr_native_core_math_version",
    capabilities_export="gr_native_core_math_capabilities_json",
)


def _candidate_output_dirs(repo_root: Path) -> Iterable[Path]:
    yield repo_root / "build" / "vs" / "x64" / "Debug"
    yield repo_root / "build" / "vs" / "x64" / "Release"
    yield repo_root / "build" / "vs" / "Win32" / "Debug"
    yield repo_root / "build" / "vs" / "Win32" / "Release"


def _candidate_paths(
    spec: NativePackageSpec,
    search_paths: Iterable[Path] | None = None,
) -> list[Path]:
    if search_paths is not None:
        return [Path(path) / spec.dll_name if Path(path).is_dir() else Path(path) for path in search_paths]

    override = os.environ.get(spec.env_var) if spec.env_var else ""
    if override:
        return [Path(override)]

    repo_root = Path(__file__).resolve().parents[3]
    return [directory / spec.dll_name for directory in _candidate_output_dirs(repo_root)]


def _load_library(path: Path) -> ctypes.CDLL:
    return ctypes.CDLL(str(path))


def query_native_package_status(
    spec: NativePackageSpec,
    search_paths: Iterable[Path] | None = None,
) -> NativePackageStatus:
    if spec.windows_only and platform.system() != "Windows":
        return NativePackageStatus(
            name=spec.name,
            available=False,
            reason=f"{spec.name} is currently a Windows native package.",
        )

    candidates = _candidate_paths(spec, search_paths)
    existing = [path for path in candidates if path.exists()]
    if not existing:
        return NativePackageStatus(
            name=spec.name,
            available=False,
            reason=f"{spec.dll_name} was not found.",
        )

    path = existing[0]
    try:
        dll = _load_library(path)
        version = ""
        capabilities: dict[str, object] | None = None
        if spec.version_export:
            version_func = getattr(dll, spec.version_export)
            version_func.restype = ctypes.c_char_p
            version = (version_func() or b"").decode("utf-8", errors="replace")
        if spec.capabilities_export:
            capabilities_func = getattr(dll, spec.capabilities_export)
            capabilities_func.restype = ctypes.c_char_p
            raw_capabilities = (capabilities_func() or b"{}").decode(
                "utf-8",
                errors="replace",
            )
            capabilities = json.loads(raw_capabilities)
    except Exception as exc:
        return NativePackageStatus(
            name=spec.name,
            available=False,
            path=str(path),
            reason=str(exc),
        )

    return NativePackageStatus(
        name=spec.name,
        available=True,
        version=version,
        capabilities=capabilities,
        path=str(path),
    )


def query_native_core_status(search_paths: Iterable[Path] | None = None) -> NativePackageStatus:
    return query_native_package_status(NATIVE_CORE_PACKAGE, search_paths)


def query_native_core_diagnostics_status(
    search_paths: Iterable[Path] | None = None,
) -> NativePackageStatus:
    return query_native_package_status(NATIVE_CORE_DIAGNOSTICS_PACKAGE, search_paths)


def query_native_core_math_status(
    search_paths: Iterable[Path] | None = None,
) -> NativePackageStatus:
    return query_native_package_status(NATIVE_CORE_MATH_PACKAGE, search_paths)


def query_runtime_shared_contracts_status(
    search_paths: Iterable[Path] | None = None,
) -> NativePackageStatus:
    return query_native_package_status(RUNTIME_SHARED_CONTRACTS_PACKAGE, search_paths)


def query_runtime_shared_descriptors_status(
    search_paths: Iterable[Path] | None = None,
) -> NativePackageStatus:
    return query_native_package_status(RUNTIME_SHARED_DESCRIPTORS_PACKAGE, search_paths)


def query_runtime_shared_resources_status(
    search_paths: Iterable[Path] | None = None,
) -> NativePackageStatus:
    return query_native_package_status(RUNTIME_SHARED_RESOURCES_PACKAGE, search_paths)


def query_renderer_contracts_status(
    search_paths: Iterable[Path] | None = None,
) -> NativePackageStatus:
    return query_native_package_status(RENDERER_CONTRACTS_PACKAGE, search_paths)


def query_renderer_null_status(
    search_paths: Iterable[Path] | None = None,
) -> NativePackageStatus:
    return query_native_package_status(RENDERER_NULL_PACKAGE, search_paths)
