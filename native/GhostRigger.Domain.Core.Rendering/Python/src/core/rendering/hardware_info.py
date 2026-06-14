"""Best-effort CPU/GPU information for renderer settings panels."""

from __future__ import annotations

from dataclasses import dataclass, field
from functools import lru_cache
import json
import os
import platform
import subprocess


_FEATURE_ALIASES = {
    "sse": ("sse",),
    "sse2": ("sse2",),
    "sse3": ("sse3", "pni"),
    "ssse3": ("ssse3",),
    "sse4_1": ("sse4_1", "sse4.1"),
    "sse4_2": ("sse4_2", "sse4.2"),
    "aes": ("aes", "aes_ni"),
    "avx": ("avx",),
    "avx2": ("avx2",),
    "fma": ("fma", "fma3"),
    "avx512": ("avx512", "avx512f"),
}


@dataclass(frozen=True)
class HardwareDiagnostics:
    cpu_name: str = ""
    physical_cores: int = 0
    logical_threads: int = 0
    architecture: str = ""
    instruction_sets: dict[str, bool] = field(default_factory=dict)
    gpu_adapter: str = ""
    renderer_backend: str = ""
    target_fps: int = 60
    cpu_optimisation_flags: tuple[str, ...] = field(default_factory=tuple)
    unavailable_reason: str = ""

    def to_dict(self) -> dict[str, object]:
        return {
            "cpu_name": self.cpu_name,
            "physical_cores": self.physical_cores,
            "logical_threads": self.logical_threads,
            "architecture": self.architecture,
            "instruction_sets": dict(self.instruction_sets),
            "gpu_adapter": self.gpu_adapter,
            "renderer_backend": self.renderer_backend,
            "target_fps": self.target_fps,
            "cpu_optimisation_flags": list(self.cpu_optimisation_flags),
            "unavailable_reason": self.unavailable_reason,
        }

    @classmethod
    def from_dict(cls, values: dict | None) -> "HardwareDiagnostics":
        payload = dict(values or {})
        instruction_sets = payload.get("instruction_sets") or {}
        optimisation_flags = payload.get("cpu_optimisation_flags") or ()
        return cls(
            cpu_name=str(payload.get("cpu_name") or ""),
            physical_cores=_safe_int(payload.get("physical_cores")),
            logical_threads=_safe_int(payload.get("logical_threads")),
            architecture=str(payload.get("architecture") or ""),
            instruction_sets=dict(instruction_sets) if isinstance(instruction_sets, dict) else {},
            gpu_adapter=str(payload.get("gpu_adapter") or ""),
            renderer_backend=str(payload.get("renderer_backend") or ""),
            target_fps=max(1, _safe_int(payload.get("target_fps")) or 60),
            cpu_optimisation_flags=tuple(str(flag) for flag in optimisation_flags),
            unavailable_reason=str(payload.get("unavailable_reason") or ""),
        )

    def lines(self) -> list[str]:
        features = ", ".join(
            name.upper().replace("_", ".")
            for name, enabled in self.instruction_sets.items()
            if enabled
        )
        if not features:
            features = "Unavailable"
        flags = ", ".join(self.cpu_optimisation_flags) or "Python-level only; NumPy/native libraries decide SIMD use"
        return [
            f"CPU: {self.cpu_name or 'Unknown'}",
            f"Cores / threads: {self.physical_cores or 'unknown'} / {self.logical_threads or 'unknown'}",
            f"Architecture: {self.architecture or 'Unknown'}",
            f"Instruction sets: {features}",
            f"GPU adapter: {self.gpu_adapter or 'Unavailable'}",
            f"Renderer backend: {self.renderer_backend or 'Unknown'}",
            f"Target FPS: {int(self.target_fps)}",
            f"CPU optimisation flags: {flags}",
        ]


def collect_hardware_diagnostics(
    *,
    renderer_diagnostics: dict | None = None,
    target_fps: int = 60,
) -> HardwareDiagnostics:
    renderer_diagnostics = dict(renderer_diagnostics or {})
    cpu_payload = _cpuinfo_payload()
    windows_cpu = _windows_processor_info()
    flags = _cpu_flags()
    instruction_sets = {
        public_name: any(alias in flags for alias in aliases)
        for public_name, aliases in _FEATURE_ALIASES.items()
    }
    backend = str(
        renderer_diagnostics.get("backend_id")
        or renderer_diagnostics.get("name")
        or renderer_diagnostics.get("api")
        or ""
    )
    return HardwareDiagnostics(
        cpu_name=_cpu_name(cpu_payload, windows_cpu),
        physical_cores=_physical_core_count(windows_cpu),
        logical_threads=_logical_thread_count(windows_cpu),
        architecture=_architecture_label(cpu_payload, windows_cpu),
        instruction_sets=instruction_sets,
        gpu_adapter=_adapter_name(renderer_diagnostics),
        renderer_backend=backend,
        target_fps=max(1, int(target_fps or 60)),
        cpu_optimisation_flags=("frame governor", "dirty overlays", "cached WGPU render queue"),
        unavailable_reason="" if flags else "instruction-set detection unavailable; using platform fallbacks",
    )


def _cpu_name(cpu_payload: dict | None = None, windows_cpu: dict | None = None) -> str:
    info = cpu_payload if cpu_payload is not None else _cpuinfo_payload()
    name = str(info.get("brand_raw") or info.get("brand") or "").strip()
    if name:
        return name
    windows_info = windows_cpu if windows_cpu is not None else _windows_processor_info()
    name = str(windows_info.get("Name") or windows_info.get("name") or "").strip()
    if name:
        return name
    try:
        import winreg  # type: ignore

        key_path = r"HARDWARE\DESCRIPTION\System\CentralProcessor\0"
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, key_path) as key:
            value, _kind = winreg.QueryValueEx(key, "ProcessorNameString")
            text = str(value or "").strip()
            if text:
                return text
    except Exception:
        pass
    for value in (platform.processor(), platform.uname().processor):
        text = str(value or "").strip()
        if text:
            return text
    return ""


def _cpu_flags() -> set[str]:
    info = _cpuinfo_payload()
    flags = {str(flag).lower().replace(".", "_") for flag in info.get("flags", []) or []}
    if flags:
        return flags
    return _windows_processor_feature_flags()


def _physical_core_count(windows_cpu: dict | None = None) -> int:
    try:
        import psutil  # type: ignore

        value = psutil.cpu_count(logical=False)
        if value:
            return int(value)
    except Exception:
        pass
    info = windows_cpu if windows_cpu is not None else _windows_processor_info()
    return _safe_int(info.get("NumberOfCores"))


def _logical_thread_count(windows_cpu: dict | None = None) -> int:
    info = windows_cpu if windows_cpu is not None else _windows_processor_info()
    value = _safe_int(info.get("NumberOfLogicalProcessors"))
    return value or int(os.cpu_count() or 0)


def _adapter_name(renderer_diagnostics: dict) -> str:
    adapter = renderer_diagnostics.get("adapter") or {}
    if isinstance(adapter, dict):
        for key in ("description", "device", "name", "vendor"):
            value = str(adapter.get(key) or "").strip()
            if value:
                return value
    details = renderer_diagnostics.get("details") or {}
    if isinstance(details, dict):
        nested = details.get("adapter") or {}
        if isinstance(nested, dict):
            for key in ("description", "device", "name", "vendor"):
                value = str(nested.get(key) or "").strip()
                if value:
                    return value
    direct = str(renderer_diagnostics.get("adapter_name") or "").strip()
    if direct:
        return direct
    return _windows_gpu_adapter_name()


@lru_cache(maxsize=1)
def _cpuinfo_payload() -> dict:
    try:
        import cpuinfo  # type: ignore

        info = cpuinfo.get_cpu_info() or {}
        return dict(info) if isinstance(info, dict) else {}
    except Exception:
        return {}


@lru_cache(maxsize=1)
def _windows_processor_info() -> dict:
    if os.name != "nt":
        return {}
    command = (
        "Get-CimInstance Win32_Processor | "
        "Select-Object -First 1 Name,Manufacturer,Architecture,NumberOfCores,NumberOfLogicalProcessors | "
        "ConvertTo-Json -Compress"
    )
    try:
        completed = subprocess.run(
            ["powershell", "-NoProfile", "-Command", command],
            capture_output=True,
            text=True,
            timeout=3.0,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        payload = json.loads((completed.stdout or "").strip() or "{}")
        if isinstance(payload, dict):
            return payload
    except Exception:
        pass
    try:
        completed = subprocess.run(
            ["wmic", "cpu", "get", "Name,Manufacturer,NumberOfCores,NumberOfLogicalProcessors", "/value"],
            capture_output=True,
            text=True,
            timeout=2.0,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        result: dict[str, object] = {}
        for line in (completed.stdout or "").splitlines():
            if "=" not in line:
                continue
            key, value = line.split("=", 1)
            if key.strip() and value.strip():
                result[key.strip()] = value.strip()
        return result
    except Exception:
        return {}


def _architecture_label(cpu_payload: dict, windows_cpu: dict) -> str:
    vendor = str(
        cpu_payload.get("vendor_id_raw")
        or cpu_payload.get("vendor_id")
        or windows_cpu.get("Manufacturer")
        or ""
    ).lower()
    raw_arch = str(cpu_payload.get("arch_string_raw") or platform.machine() or platform.architecture()[0] or "").strip()
    key = raw_arch.lower().replace("-", "_")
    if key in {"amd64", "x86_64", "x64"}:
        if "intel" in vendor or "genuineintel" in vendor:
            return "Intel64 (x86-64)"
        if "amd" in vendor or "authenticamd" in vendor:
            return "AMD64 (x86-64)"
        return "x86-64"
    if key in {"arm64", "aarch64"}:
        return "ARM64"
    return raw_arch or "Unknown"


def _windows_processor_feature_flags() -> set[str]:
    if os.name != "nt":
        return set()
    try:
        import ctypes

        is_present = ctypes.windll.kernel32.IsProcessorFeaturePresent
        mapping = {
            "sse": 6,
            "sse2": 10,
            "sse3": 13,
            "ssse3": 36,
            "sse4_1": 37,
            "sse4_2": 38,
            "avx": 39,
            "avx2": 40,
            "avx512": 41,
        }
        return {name for name, feature_id in mapping.items() if bool(is_present(feature_id))}
    except Exception:
        return set()


@lru_cache(maxsize=1)
def _windows_gpu_adapter_name() -> str:
    if os.name != "nt":
        return ""
    names: list[str] = []
    command = (
        "Get-CimInstance Win32_VideoController | "
        "Select-Object Name,AdapterCompatibility | ConvertTo-Json -Compress"
    )
    try:
        completed = subprocess.run(
            ["powershell", "-NoProfile", "-Command", command],
            capture_output=True,
            text=True,
            timeout=3.0,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        payload = json.loads((completed.stdout or "").strip() or "[]")
        rows = payload if isinstance(payload, list) else [payload]
        for row in rows:
            if not isinstance(row, dict):
                continue
            name = str(row.get("Name") or "").strip()
            if name and name not in names:
                names.append(name)
    except Exception:
        pass
    if not names:
        try:
            completed = subprocess.run(
                ["wmic", "path", "win32_VideoController", "get", "Name", "/value"],
                capture_output=True,
                text=True,
                timeout=2.0,
                creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
            )
            for line in (completed.stdout or "").splitlines():
                if line.lower().startswith("name="):
                    name = line.split("=", 1)[1].strip()
                    if name and name not in names:
                        names.append(name)
        except Exception:
            pass
    if not names:
        return ""
    preferred = [
        name for name in names
        if any(token in name.lower() for token in ("nvidia", "geforce", "radeon", "amd"))
    ]
    ordered = preferred + [name for name in names if name not in preferred]
    return "; ".join(ordered)


def _safe_int(value: object) -> int:
    try:
        return int(value or 0)
    except Exception:
        return 0
