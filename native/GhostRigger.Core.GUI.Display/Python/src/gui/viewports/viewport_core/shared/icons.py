"""Viewport icon and GPU-brand helpers."""

from __future__ import annotations

from .dependencies import Path, QtCore, QtGui, subprocess, normalize_viewport_navigation_profile

_GUI_DIR = Path(__file__).resolve().parents[3]
_ICON_DIR = _GUI_DIR / "icons"


def _icon_dirs() -> tuple[Path, ...]:
    dirs = [_ICON_DIR]
    for parent in Path(__file__).resolve().parents:
        runtime_icons = parent / "native" / "GhostRigger.Native.Core.Host.vcxproj" / "RuntimePayload" / "src" / "gui" / "icons"
        if runtime_icons.exists():
            dirs.append(runtime_icons)
            break
    return tuple(dict.fromkeys(dirs))


def _icon(name: str) -> QtGui.QIcon:
    for icon_dir in _icon_dirs():
        for suffix in (".svg", "_16.png", "_24.png", ".png"):
            path = icon_dir / f"{name}{suffix}"
            if path.exists():
                return QtGui.QIcon(path.as_posix())
    return _generated_fallback_icon(name)


def _gpu_brand_icon(brand: str) -> QtGui.QIcon:
    for icon_dir in _icon_dirs():
        path = icon_dir / "gpu_branding" / f"{brand}.png"
        if path.exists():
            return QtGui.QIcon(path.as_posix())
    return QtGui.QIcon()


def _branded_control_icon(name: str) -> QtGui.QIcon:
    for icon_dir in _icon_dirs():
        path = icon_dir / "branded_controls" / f"{name}.png"
        if path.exists():
            return QtGui.QIcon(path.as_posix())
    return _generated_fallback_icon(name)


def _fallback_label(name: str) -> str:
    tokens = [token for token in str(name or "").replace("-", "_").split("_") if token]
    if not tokens:
        return "?"
    skip = {"viewport", "button", "icon", "open"}
    useful = [token for token in tokens if token.lower() not in skip] or tokens
    if len(useful) == 1:
        return useful[0][:2].upper()
    return "".join(token[0] for token in useful[:2]).upper()


def _generated_fallback_icon(name: str, size: int = 22) -> QtGui.QIcon:
    pixel_size = max(18, min(32, int(size or 22)))
    pixmap = QtGui.QPixmap(pixel_size, pixel_size)
    pixmap.fill(QtCore.Qt.transparent)

    accent = QtGui.QColor("#38bdf8")
    background = QtGui.QColor("#132225")
    border = QtGui.QColor(accent)
    border.setAlpha(220)
    background.setAlpha(210)

    painter = QtGui.QPainter(pixmap)
    painter.setRenderHint(QtGui.QPainter.Antialiasing, True)
    rect = QtCore.QRectF(1.0, 1.0, pixel_size - 2.0, pixel_size - 2.0)
    painter.setPen(QtGui.QPen(border, 1.2))
    painter.setBrush(QtGui.QBrush(background))
    painter.drawRoundedRect(rect, 3.0, 3.0)
    font = QtGui.QFont()
    font.setBold(True)
    font.setPointSize(max(6, int(pixel_size * 0.34)))
    painter.setFont(font)
    painter.setPen(accent)
    painter.drawText(pixmap.rect(), QtCore.Qt.AlignCenter, _fallback_label(name))
    painter.end()
    return QtGui.QIcon(pixmap)


def _detect_gpu_brand() -> str:
    try:
        output = subprocess.run(
            [
                "powershell",
                "-NoProfile",
                "-Command",
                "Get-CimInstance Win32_VideoController | Select-Object -ExpandProperty Name",
            ],
            capture_output=True,
            text=True,
            timeout=1.5,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        text = f"{output.stdout}\n{output.stderr}".lower()
    except Exception:
        text = ""
    if any(token in text for token in ("nvidia", "geforce", "quadro", "rtx", "gtx")):
        return "nvidia"
    if any(token in text for token in ("amd", "radeon", "rx ", "firepro")):
        return "amd"
    return "generic"


def _gpu_icon_name() -> str:
    brand = _detect_gpu_brand()
    if brand == "nvidia":
        return "nvidia"
    if brand == "amd":
        return "amd"
    return "generic"


def _gpu_icon() -> QtGui.QIcon:
    brand = _gpu_icon_name()
    if brand in {"nvidia", "amd"}:
        icon = _gpu_brand_icon(brand)
        if not icon.isNull():
            return icon
    return _icon("viewport_gpu")


def _navigation_profile_icon(profile: object) -> QtGui.QIcon:
    profile_key = normalize_viewport_navigation_profile(profile)
    if profile_key == "3dsmax":
        return _branded_control_icon("3dsmax")
    if profile_key == "blender":
        return _branded_control_icon("blender")
    if profile_key == "maya":
        return _branded_control_icon("maya")
    return _generated_fallback_icon(str(profile_key or "navigation"))

__all__ = tuple(name for name in globals() if not name.startswith("__"))
