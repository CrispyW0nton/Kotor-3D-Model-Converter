from __future__ import annotations

from pathlib import Path

from src.adapters.native_core.package_registry import (
    NATIVE_CORE_DIAGNOSTICS_PACKAGE,
    NATIVE_CORE_MATH_PACKAGE,
    NATIVE_CORE_PACKAGE,
    RUNTIME_SHARED_CONTRACTS_PACKAGE,
    NativePackageSpec,
    NativePackageStatus,
    query_native_core_diagnostics_status,
    query_native_core_math_status,
    query_native_core_status,
    query_native_package_status,
    query_runtime_shared_contracts_status,
)


def test_native_core_status_reports_missing_package(tmp_path: Path) -> None:
    status = query_native_core_status([tmp_path])

    assert isinstance(status, NativePackageStatus)
    assert status.name == "GhostRigger.Native.NativeCore"
    assert status.available is False
    assert "not found" in status.reason or "Windows native package" in status.reason


def test_generic_native_package_status_reports_package_specific_missing_dll(tmp_path: Path) -> None:
    spec = NativePackageSpec(
        name="GhostRigger.Runtime.Shared.Example",
        dll_name="GhostRigger.Runtime.Shared.Example.dll",
        env_var="GHOSTRIGGER_RUNTIME_SHARED_EXAMPLE",
    )

    status = query_native_package_status(spec, [tmp_path])

    assert status.name == "GhostRigger.Runtime.Shared.Example"
    assert status.available is False
    assert (
        "GhostRigger.Runtime.Shared.Example.dll was not found." in status.reason
        or "Windows native package" in status.reason
    )


def test_runtime_shared_contracts_status_uses_shared_registry_path(tmp_path: Path) -> None:
    status = query_runtime_shared_contracts_status([tmp_path])

    assert status.name == "GhostRigger.Runtime.Shared.Contracts"
    assert status.available is False
    assert (
        "GhostRigger.Runtime.Shared.Contracts.dll was not found." in status.reason
        or "Windows native package" in status.reason
    )


def test_native_core_diagnostics_status_uses_shared_registry_path(tmp_path: Path) -> None:
    status = query_native_core_diagnostics_status([tmp_path])

    assert status.name == "GhostRigger.Native.NativeCore.Diagnostics"
    assert status.available is False
    assert (
        "GhostRigger.Native.NativeCore.Diagnostics.dll was not found." in status.reason
        or "Windows native package" in status.reason
    )


def test_native_core_math_status_uses_shared_registry_path(tmp_path: Path) -> None:
    status = query_native_core_math_status([tmp_path])

    assert status.name == "GhostRigger.Native.NativeCore.Math"
    assert status.available is False
    assert (
        "GhostRigger.Native.NativeCore.Math.dll was not found." in status.reason
        or "Windows native package" in status.reason
    )


def test_native_core_package_registry_exports_stable_status_fields() -> None:
    status = NativePackageStatus(
        name="GhostRigger.Native.NativeCore",
        available=True,
        version="0.1.0",
        capabilities={"shared_handles": True},
        path="native.dll",
    )

    assert status.name == "GhostRigger.Native.NativeCore"
    assert status.available is True
    assert status.version == "0.1.0"
    assert status.capabilities == {"shared_handles": True}
    assert status.path == "native.dll"


def test_native_core_package_spec_names_current_core_contract() -> None:
    assert NATIVE_CORE_PACKAGE.name == "GhostRigger.Native.NativeCore"
    assert NATIVE_CORE_PACKAGE.dll_name == "GhostRigger.Native.NativeCore.dll"
    assert NATIVE_CORE_PACKAGE.env_var == "GHOSTRIGGER_NATIVE_CORE"
    assert NATIVE_CORE_PACKAGE.version_export == "gr_native_core_version"
    assert NATIVE_CORE_PACKAGE.capabilities_export == "gr_native_core_capabilities_json"


def test_native_core_diagnostics_package_spec_names_current_contract() -> None:
    assert NATIVE_CORE_DIAGNOSTICS_PACKAGE.name == "GhostRigger.Native.NativeCore.Diagnostics"
    assert NATIVE_CORE_DIAGNOSTICS_PACKAGE.dll_name == "GhostRigger.Native.NativeCore.Diagnostics.dll"
    assert NATIVE_CORE_DIAGNOSTICS_PACKAGE.env_var == "GHOSTRIGGER_NATIVE_CORE_DIAGNOSTICS"
    assert NATIVE_CORE_DIAGNOSTICS_PACKAGE.version_export == "gr_native_core_diagnostics_version"
    assert (
        NATIVE_CORE_DIAGNOSTICS_PACKAGE.capabilities_export
        == "gr_native_core_diagnostics_capabilities_json"
    )


def test_native_core_math_package_spec_names_current_contract() -> None:
    assert NATIVE_CORE_MATH_PACKAGE.name == "GhostRigger.Native.NativeCore.Math"
    assert NATIVE_CORE_MATH_PACKAGE.dll_name == "GhostRigger.Native.NativeCore.Math.dll"
    assert NATIVE_CORE_MATH_PACKAGE.env_var == "GHOSTRIGGER_NATIVE_CORE_MATH"
    assert NATIVE_CORE_MATH_PACKAGE.version_export == "gr_native_core_math_version"
    assert NATIVE_CORE_MATH_PACKAGE.capabilities_export == "gr_native_core_math_capabilities_json"


def test_runtime_shared_contracts_package_spec_names_current_contract() -> None:
    assert RUNTIME_SHARED_CONTRACTS_PACKAGE.name == "GhostRigger.Runtime.Shared.Contracts"
    assert RUNTIME_SHARED_CONTRACTS_PACKAGE.dll_name == "GhostRigger.Runtime.Shared.Contracts.dll"
    assert RUNTIME_SHARED_CONTRACTS_PACKAGE.env_var == "GHOSTRIGGER_RUNTIME_SHARED_CONTRACTS"
    assert RUNTIME_SHARED_CONTRACTS_PACKAGE.version_export == "gr_runtime_shared_contracts_version"
    assert (
        RUNTIME_SHARED_CONTRACTS_PACKAGE.capabilities_export
        == "gr_runtime_shared_contracts_capabilities_json"
    )
