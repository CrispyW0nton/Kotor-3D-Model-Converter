"""Scaffold helpers for custom Qt viewport widgets.

This module is intentionally headless so it can be used from tests, scripts,
or the embedded GhostRigger Python terminal without constructing Qt widgets.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
import re


_VALID_KINDS = {"widget", "mixin"}


@dataclass(frozen=True)
class ViewportWidgetScaffoldResult:
    """Result returned by :func:`create_custom_viewport_widget`."""

    kind: str
    module_name: str
    class_name: str
    path: str
    created: bool
    public_export: bool
    next_steps: tuple[str, ...]

    def as_dict(self) -> dict[str, object]:
        return asdict(self)


def _snake_case(value: str) -> str:
    text = str(value or "").strip()
    if not text:
        raise ValueError("name is required.")
    text = re.sub(r"([a-z0-9])([A-Z])", r"\1_\2", text)
    text = re.sub(r"[^0-9A-Za-z]+", "_", text)
    text = re.sub(r"_+", "_", text).strip("_").lower()
    if not text:
        raise ValueError("name must contain at least one letter or number.")
    if text[0].isdigit():
        text = f"widget_{text}"
    return text


def _pascal_case(module_name: str) -> str:
    return "".join(part.capitalize() for part in module_name.split("_") if part)


def _widget_template(module_name: str, class_name: str) -> str:
    object_name = class_name
    title = module_name.replace("_", " ").title()
    return f'''"""Custom viewport widget: {title}."""

from __future__ import annotations

from ..shared.dependencies import QtWidgets


class {class_name}(QtWidgets.QWidget):
    """Focused custom widget for the GhostRigger viewport."""

    def __init__(self, parent: QtWidgets.QWidget | None = None):
        super().__init__(parent)
        self.setObjectName("{object_name}")
        self._build()

    def _build(self) -> None:
        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

    def apply_ghost_theme(self, theme) -> None:
        """Apply the active GhostRigger theme when custom painting is needed."""

    def apply_ghost_layout(self, layout) -> None:
        """Apply layout metrics when this widget owns stable dimensions."""


__all__ = ("{class_name}",)
'''


def _mixin_template(module_name: str, class_name: str) -> str:
    title = module_name.replace("_", " ").title()
    return f'''"""Custom viewport behavior mixin: {title}."""

from __future__ import annotations

from ..shared import *  # noqa: F401,F403


class {class_name}:
    """Focused behavior slice for QtViewportWidget."""

    def _install_{module_name}_hooks(self) -> None:
        """Wire this mixin from QtViewportWidget.__init__ when needed."""


__all__ = ("{class_name}",)
'''


def create_custom_viewport_widget(
    name: str,
    *,
    kind: str = "widget",
    overwrite: bool = False,
    public_export: bool = False,
    target_root: str | Path | None = None,
) -> dict[str, object]:
    """Create a focused viewport widget or mixin module.

    Parameters
    ----------
    name:
        Human or code name for the module/class, such as ``"orbit gizmo"`` or
        ``"OrbitGizmoWidget"``.
    kind:
        ``"widget"`` creates a ``QtWidgets.QWidget`` subclass. ``"mixin"``
        creates a behavior mixin intended for ``QtViewportWidget`` composition.
    overwrite:
        If false, existing files are preserved and a ``FileExistsError`` is
        raised.
    public_export:
        Adds public-export next-step guidance to the returned result. The
        scaffolder does not edit lazy facades automatically inside a live app.
    target_root:
        Optional widgets directory override for tests or external tooling.
    """

    normalized_kind = str(kind or "widget").strip().lower()
    if normalized_kind not in _VALID_KINDS:
        raise ValueError(f"kind must be one of {sorted(_VALID_KINDS)!r}.")

    module_name = _snake_case(name)
    class_name = _pascal_case(module_name)
    if normalized_kind == "widget" and not class_name.endswith("Widget"):
        class_name = f"{class_name}Widget"
    if normalized_kind == "mixin" and not class_name.endswith("Mixin"):
        class_name = f"{class_name}Mixin"

    widgets_dir = Path(target_root) if target_root is not None else Path(__file__).resolve().parent / "widgets"
    widgets_dir.mkdir(parents=True, exist_ok=True)
    path = widgets_dir / f"{module_name}.py"
    if path.exists() and not overwrite:
        raise FileExistsError(f"Viewport widget module already exists: {path}")

    template = (
        _widget_template(module_name, class_name)
        if normalized_kind == "widget"
        else _mixin_template(module_name, class_name)
    )
    path.write_text(template, encoding="utf-8", newline="")

    next_steps = [
        f"Edit {path.as_posix()} and keep the implementation focused.",
    ]
    if normalized_kind == "mixin":
        next_steps.append("Add the mixin to QtViewportWidget in widgets/viewport_widget.py when the behavior is ready.")
    if public_export:
        next_steps.append("Add the class to widgets/__init__.py, viewport_core/widget.py, and qt_viewport.py lazy exports.")
    next_steps.append("Add or update targeted source-contract tests for the new module.")

    return ViewportWidgetScaffoldResult(
        kind=normalized_kind,
        module_name=module_name,
        class_name=class_name,
        path=str(path),
        created=True,
        public_export=bool(public_export),
        next_steps=tuple(next_steps),
    ).as_dict()


__all__ = ("ViewportWidgetScaffoldResult", "create_custom_viewport_widget")
