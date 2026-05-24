"""Renderer settings read from GhostRigger settings.json."""

from __future__ import annotations

from dataclasses import dataclass

from src.gui.rendering.renderer_backend import RendererBackend, normalize_renderer_backend


@dataclass(frozen=True)
class RendererSettings:
    backend: RendererBackend = RendererBackend.AUTOMATIC
    preferred_windows_backend: RendererBackend = RendererBackend.MODERNGL_GL330
    allow_fallback: bool = True
    show_renderer_diagnostics: bool = True
    force_safe_mode: bool = False

    @classmethod
    def from_settings(cls, settings: dict | None) -> "RendererSettings":
        values = dict((settings or {}).get("renderer") or {})
        return cls(
            backend=normalize_renderer_backend(values.get("backend", RendererBackend.AUTOMATIC.value)),
            preferred_windows_backend=normalize_renderer_backend(
                values.get("preferred_windows_backend", RendererBackend.MODERNGL_GL330.value)
            ),
            allow_fallback=bool(values.get("allow_fallback", True)),
            show_renderer_diagnostics=bool(values.get("show_renderer_diagnostics", True)),
            force_safe_mode=bool(values.get("force_safe_mode", False)),
        )

    def to_settings_dict(self) -> dict[str, object]:
        return {
            "backend": self.backend.value,
            "preferred_windows_backend": self.preferred_windows_backend.value,
            "allow_fallback": self.allow_fallback,
            "show_renderer_diagnostics": self.show_renderer_diagnostics,
            "force_safe_mode": self.force_safe_mode,
        }

    @staticmethod
    def apply_defaults(settings: dict) -> dict:
        renderer = settings.setdefault("renderer", {})
        defaults = RendererSettings().to_settings_dict()
        for key, value in defaults.items():
            renderer.setdefault(key, value)
        renderer["backend"] = normalize_renderer_backend(renderer.get("backend")).value
        renderer["preferred_windows_backend"] = normalize_renderer_backend(
            renderer.get("preferred_windows_backend")
        ).value
        return settings
