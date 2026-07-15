"""Renderer backend factory and fallback proxy."""

from __future__ import annotations

import logging
import inspect
from typing import Iterable

from src.adapters.rendering.moderngl_renderer import ModernGLRenderer
from src.adapters.rendering.null_renderer import NullDiagnosticRenderer
from src.adapters.rendering.pygfx_core.renderer import PygfxViewportRenderer
from src.core.rendering.renderer_backend import (
    RendererBackend,
    SUPPORTED_RENDERER_BACKENDS,
    renderer_backend_label,
    supported_renderer_backend,
)
from src.core.rendering.renderer_capabilities import RendererCapabilities
from src.core.rendering.renderer_settings import RendererSettings
from src.core.ports import ViewportRendererPort
from src.adapters.rendering.wgpu_core.renderer import WgpuRenderer

log = logging.getLogger(__name__)


def _renderer_for_backend(backend: RendererBackend, settings: RendererSettings | None = None) -> ViewportRendererPort:
    backend = supported_renderer_backend(backend)
    if backend == RendererBackend.MODERNGL_GL330:
        return ModernGLRenderer()
    if backend == RendererBackend.WGPU_D3D12:
        return WgpuRenderer(RendererBackend.WGPU_D3D12, settings=settings)
    if backend == RendererBackend.PYGFX_WGPU:
        return PygfxViewportRenderer(settings=settings)
    if backend == RendererBackend.NULL_DIAGNOSTIC:
        return NullDiagnosticRenderer()
    return ModernGLRenderer()


def _dedupe(backends: Iterable[RendererBackend]) -> list[RendererBackend]:
    result: list[RendererBackend] = []
    for backend in backends:
        if backend not in result:
            result.append(backend)
    return result


def _render_kwargs_for(renderer, kwargs: dict) -> dict:
    try:
        signature = inspect.signature(renderer.render)
    except (TypeError, ValueError):
        return kwargs
    parameters = signature.parameters.values()
    if any(parameter.kind == inspect.Parameter.VAR_KEYWORD for parameter in parameters):
        return kwargs
    accepted = {
        name
        for name, parameter in signature.parameters.items()
        if parameter.kind in {inspect.Parameter.POSITIONAL_OR_KEYWORD, inspect.Parameter.KEYWORD_ONLY}
    }
    return {key: value for key, value in kwargs.items() if key in accepted}


def fallback_order(settings: RendererSettings) -> list[RendererBackend]:
    if settings.force_safe_mode:
        return [RendererBackend.MODERNGL_GL330, RendererBackend.NULL_DIAGNOSTIC]

    requested = supported_renderer_backend(settings.backend)

    if requested == RendererBackend.MODERNGL_GL330:
        return [RendererBackend.MODERNGL_GL330, RendererBackend.NULL_DIAGNOSTIC]

    if not settings.allow_fallback:
        return [requested, RendererBackend.NULL_DIAGNOSTIC]

    if requested == RendererBackend.PYGFX_WGPU:
        return _dedupe(
            [
                requested,
                RendererBackend.WGPU_D3D12,
                RendererBackend.MODERNGL_GL330,
                RendererBackend.NULL_DIAGNOSTIC,
            ]
        )
    return _dedupe(
        [
            requested,
            RendererBackend.MODERNGL_GL330,
            RendererBackend.NULL_DIAGNOSTIC,
        ]
    )


def renderer_capabilities_snapshot() -> list[RendererCapabilities]:
    backends = list(SUPPORTED_RENDERER_BACKENDS)
    caps: list[RendererCapabilities] = []
    for backend in backends:
        caps.append(_renderer_for_backend(backend).get_capabilities())
    return caps


class FallbackViewportRenderer(ViewportRendererPort):
    """GpuRenderer-compatible proxy that selects and falls back between backends."""

    _INTERNAL_ATTRS = {
        "_settings",
        "_order",
        "_active",
        "_active_backend",
        "_failed",
        "_pending_attrs",
        "_last_diagnostics",
        "_surface_widget",
    }

    def __init__(self, settings: RendererSettings | None = None):
        object.__setattr__(self, "_settings", settings or RendererSettings())
        object.__setattr__(self, "_order", fallback_order(settings or RendererSettings()))
        object.__setattr__(self, "_active", None)
        object.__setattr__(self, "_active_backend", None)
        object.__setattr__(self, "_failed", {})
        object.__setattr__(self, "_pending_attrs", {})
        object.__setattr__(self, "_last_diagnostics", {})
        object.__setattr__(self, "_surface_widget", None)
        log.info("RendererFactory: Requested backend = %s", self._order[0].name)

    @property
    def name(self) -> str:
        active = object.__getattribute__(self, "_active")
        return getattr(active, "name", "Renderer Factory")

    @property
    def backend_id(self) -> str:
        active = object.__getattribute__(self, "_active")
        if active is None:
            order = object.__getattribute__(self, "_order")
            return order[0].value if order else ""
        return getattr(active, "backend_id", "")

    def __getattr__(self, name: str):
        active = object.__getattribute__(self, "_active")
        if active is not None and hasattr(active, name):
            return getattr(active, name)
        pending = object.__getattribute__(self, "_pending_attrs")
        if name in pending:
            return pending[name]
        raise AttributeError(name)

    def __setattr__(self, name: str, value) -> None:
        if name in self._INTERNAL_ATTRS:
            object.__setattr__(self, name, value)
            return
        pending = object.__getattribute__(self, "_pending_attrs")
        pending[name] = value
        active = object.__getattribute__(self, "_active")
        if active is not None:
            setattr(active, name, value)

    def _apply_pending(self, renderer) -> None:
        for name, value in object.__getattribute__(self, "_pending_attrs").items():
            try:
                if name == "_pending_theme" and hasattr(renderer, "set_theme_colors"):
                    renderer.set_theme_colors(value)
                    continue
                if name == "_pending_native_palette" and hasattr(renderer, "set_native_palette_colors"):
                    renderer.set_native_palette_colors(**value)
                    continue
                setattr(renderer, name, value)
            except Exception:
                log.debug("RendererFactory: could not apply renderer attribute %s", name, exc_info=True)

    def _activate_next(self) -> ViewportRendererPort:
        failed = object.__getattribute__(self, "_failed")
        for backend in object.__getattribute__(self, "_order"):
            if backend in failed:
                continue
            renderer = _renderer_for_backend(backend, object.__getattribute__(self, "_settings"))
            caps = renderer.get_capabilities()
            if not renderer.is_available():
                reason = caps.reason or "not available"
                failed[backend] = reason
                log.info("RendererFactory: %s unavailable: %s", backend.name, reason)
                continue
            self._apply_pending(renderer)
            object.__setattr__(self, "_active", renderer)
            object.__setattr__(self, "_active_backend", backend)
            log.info("RendererFactory: Falling back to %s" if failed else "RendererFactory: Using %s", backend.name)
            return renderer
        renderer = NullDiagnosticRenderer()
        self._apply_pending(renderer)
        object.__setattr__(self, "_active", renderer)
        object.__setattr__(self, "_active_backend", RendererBackend.NULL_DIAGNOSTIC)
        log.info("RendererFactory: Falling back to NULL_DIAGNOSTIC")
        return renderer

    @property
    def active_renderer(self) -> ViewportRendererPort | None:
        return object.__getattribute__(self, "_active")

    @property
    def active_backend(self):
        return object.__getattribute__(self, "_active_backend")

    def create_surface_widget(self, parent=None):
        cached = object.__getattribute__(self, "_surface_widget")
        if cached is not None:
            return cached
        renderer = object.__getattribute__(self, "_active") or self._activate_next()
        create = getattr(renderer, "create_surface_widget", None)
        if callable(create):
            widget = create(parent)
        else:
            from PySide6 import QtCore, QtWidgets

            widget = QtWidgets.QLabel("Empty Scene", parent)
            widget.setAlignment(QtCore.Qt.AlignCenter)
            widget.setFocusPolicy(QtCore.Qt.StrongFocus)
            widget.setMouseTracking(True)
        object.__setattr__(self, "_surface_widget", widget)
        return widget

    def initialize(self, viewport_widget=None, scene_context=None) -> None:
        renderer = object.__getattribute__(self, "_active") or self._activate_next()
        initialize = getattr(renderer, "initialize", None)
        if callable(initialize):
            initialize(viewport_widget, scene_context)

    def render(self, scene, camera, W: int, H: int, *args, **kwargs):
        while True:
            renderer = object.__getattribute__(self, "_active") or self._activate_next()
            backend = object.__getattribute__(self, "_active_backend")
            try:
                result = renderer.render(scene, camera, W, H, *args, **_render_kwargs_for(renderer, kwargs))
            except Exception as exc:
                result = None
                object.__getattribute__(self, "_failed")[backend] = str(exc)
                log.info("RendererFactory: %s failed during render: %s", getattr(backend, "name", backend), exc)
            if result is not None:
                diagnostics = renderer.get_diagnostics() if hasattr(renderer, "get_diagnostics") else {}
                object.__setattr__(self, "_last_diagnostics", diagnostics)
                if diagnostics:
                    log.debug("RendererDiagnostics: %s", diagnostics)
                return result
            object.__getattribute__(self, "_failed")[backend] = "render returned no image"
            if backend == RendererBackend.NULL_DIAGNOSTIC:
                return None
            shutdown = getattr(renderer, "shutdown", None)
            if callable(shutdown):
                shutdown()
            object.__setattr__(self, "_active", None)
            log.info("RendererFactory: %s unavailable: render returned no image", getattr(backend, "name", backend))

    def set_settings(self, settings: RendererSettings) -> None:
        if settings == object.__getattribute__(self, "_settings"):
            return
        old = object.__getattribute__(self, "_active")
        if old is not None:
            shutdown = getattr(old, "shutdown", None)
            if callable(shutdown):
                shutdown()
        object.__setattr__(self, "_settings", settings)
        object.__setattr__(self, "_order", fallback_order(settings))
        object.__setattr__(self, "_active", None)
        object.__setattr__(self, "_active_backend", None)
        object.__setattr__(self, "_failed", {})
        object.__setattr__(self, "_last_diagnostics", {})
        object.__setattr__(self, "_surface_widget", None)
        log.info("RendererFactory: Requested backend = %s", self._order[0].name)

    def shutdown(self) -> None:
        active = object.__getattribute__(self, "_active")
        if active is not None:
            shutdown = getattr(active, "shutdown", None)
            if callable(shutdown):
                shutdown()
        object.__setattr__(self, "_active", None)
        object.__setattr__(self, "_surface_widget", None)

    def release(self) -> None:
        self.shutdown()

    def clear_caches(self) -> None:
        active = object.__getattribute__(self, "_active")
        if active is not None and hasattr(active, "clear_caches"):
            active.clear_caches()

    def reset_framebuffers(self) -> None:
        active = object.__getattribute__(self, "_active")
        if active is not None and hasattr(active, "reset_framebuffers"):
            active.reset_framebuffers()

    def update_texture_regions(self, texture_name: str, image, regions, *, finalize: bool = True) -> bool:
        """Delegate a targeted live-texture write to the active backend."""
        active = object.__getattribute__(self, "_active")
        update = getattr(active, "update_texture_regions", None) if active is not None else None
        if callable(update):
            return bool(update(texture_name, image, regions, finalize=bool(finalize)))
        return False

    def invalidate_texture(self, texture_name: str, image=None) -> bool:
        """Targeted fallback for backends without partial texture writes."""
        active = object.__getattribute__(self, "_active")
        invalidate = getattr(active, "invalidate_texture", None) if active is not None else None
        if callable(invalidate):
            return bool(invalidate(texture_name, image=image))
        return False

    def invalidate_node(self, node) -> None:
        active = object.__getattribute__(self, "_active")
        if active is not None and hasattr(active, "invalidate_node"):
            active.invalidate_node(node)

    def invalidate_node_cache(self) -> None:
        active = object.__getattribute__(self, "_active")
        if active is not None and hasattr(active, "invalidate_node_cache"):
            active.invalidate_node_cache()

    def invalidate_transform_cache(self, reason: str = "transforms changed") -> None:
        active = object.__getattribute__(self, "_active")
        if active is None:
            return
        invalidate = getattr(active, "invalidate_transform_cache", None)
        if callable(invalidate):
            invalidate(reason)
        elif hasattr(active, "invalidate_node_cache"):
            active.invalidate_node_cache()

    def invalidate_all(self) -> None:
        active = object.__getattribute__(self, "_active")
        if active is not None and hasattr(active, "invalidate_all"):
            active.invalidate_all()

    def set_theme_colors(self, theme) -> None:
        object.__getattribute__(self, "_pending_attrs")["_pending_theme"] = theme
        active = object.__getattribute__(self, "_active")
        if active is not None and hasattr(active, "set_theme_colors"):
            active.set_theme_colors(theme)

    def set_native_palette_colors(self, *, base, text, highlight) -> None:
        object.__getattribute__(self, "_pending_attrs")["_pending_native_palette"] = {
            "base": base,
            "text": text,
            "highlight": highlight,
        }
        active = object.__getattribute__(self, "_active")
        if active is not None and hasattr(active, "set_native_palette_colors"):
            active.set_native_palette_colors(base=base, text=text, highlight=highlight)

    def get_capabilities(self) -> RendererCapabilities:
        active = object.__getattribute__(self, "_active")
        if active is not None and hasattr(active, "get_capabilities"):
            return active.get_capabilities()
        return RendererCapabilities(
            backend_id=self.backend_id,
            name=self.name,
            available=True,
            reason="Backend will be selected on first render",
        )

    def is_available(self) -> bool:
        return True

    def get_diagnostics(self) -> dict:
        active = object.__getattribute__(self, "_active")
        if active is not None and hasattr(active, "get_diagnostics"):
            return active.get_diagnostics()
        return dict(object.__getattribute__(self, "_last_diagnostics"))


def create_viewport_renderer(settings: RendererSettings | dict | None = None) -> ViewportRendererPort:
    if isinstance(settings, dict) or settings is None:
        settings = RendererSettings.from_settings(settings or {})
    return FallbackViewportRenderer(settings)
