"""Qt icon manager for GhostRigger.

This mirrors ``icon_manager.py`` for the Qt migration: icons are loaded from
``src/gui/icons`` as ``QIcon`` objects and button/tab helpers keep the same
label-to-icon convention used by the legacy Tk UI.
"""

from __future__ import annotations

import unicodedata
from pathlib import Path
from typing import Optional

from PySide6 import QtGui


ICONS_DIR = Path(__file__).resolve().parents[1] / "icons"
_cache: dict[str, QtGui.QIcon] = {}


class I:
    NEW_SCENE = "new_scene"
    OPEN = "open"
    SAVE = "save"
    IMPORT = "import"
    EXPORT = "export"
    AUTORIG = "autorig"
    SETTINGS = "settings"
    REFRESH = "refresh"
    CLOTH = "cloth"
    MODULAR = "modular"
    DIAG = "diag"
    TEXTURE = "texture"
    LIBRARY = "library"
    SEARCH = "search"
    SKELETON = "skeleton"
    PROPS = "props"
    ANIMS = "anims"
    SEQUENCE = "sequence"
    LIGHTS = "lights"
    CAMERAS = "cameras"
    RIG = "rig"
    NORMALMAP = "normalmap"
    RESOURCES = "resources"
    TWODA = "twoda"
    LOGO = "logo"
    CLOSE = "close"
    LOADMODEL = "loadmodel"
    WEIGHTPAINT = "weightpaint"
    CHARBUILDER = "charbuilder"
    TEMPLATE = "template"
    SELECTALL = "selectall"
    HEAD = "head"
    BODY = "body"
    CAT_CREATURE = "cat_creature"
    CAT_CHARACTER = "cat_character"
    CAT_ITEM = "cat_item"
    CAT_MODULE = "cat_module"
    CAT_OTHER = "cat_other"


LABEL_TO_ICON: dict[str, str] = {
    "new scene": I.NEW_SCENE,
    "open": I.OPEN,
    "save": I.SAVE,
    "import": I.IMPORT,
    "export": I.EXPORT,
    "auto-rig": I.AUTORIG,
    "autorig": I.AUTORIG,
    "rig": I.RIG,
    "settings": I.SETTINGS,
    "refresh": I.REFRESH,
    "cloth": I.CLOTH,
    "modular": I.MODULAR,
    "modules": I.MODULAR,
    "diag": I.DIAG,
    "tex": I.TEXTURE,
    "texture": I.TEXTURE,
    "library": I.LIBRARY,
    "nodes": I.SKELETON,
    "skeleton": I.SKELETON,
    "2da": I.TWODA,
    "2das": I.TWODA,
    "resources": I.RESOURCES,
    "props": I.PROPS,
    "properties": I.PROPS,
    "anims": I.ANIMS,
    "anim": I.ANIMS,
    "sequence": I.SEQUENCE,
    "lights": I.LIGHTS,
    "cameras": I.CAMERAS,
    "normalmap": I.NORMALMAP,
    "normmap": I.NORMALMAP,
    "search": I.SEARCH,
    "load": I.LOADMODEL,
    "load model": I.LOADMODEL,
    "extract": I.OPEN,
    "close": I.CLOSE,
    "clear": I.CLOSE,
    "scan": I.REFRESH,
    "deep scan": I.REFRESH,
    "auto-detect": I.SEARCH,
    "copy": I.PROPS,
    "character builder": I.CHARBUILDER,
    "charbuilder": I.CHARBUILDER,
    "template": I.TEMPLATE,
    "body": I.BODY,
    "head": I.HEAD,
    "select all": I.SELECTALL,
    "weight": I.WEIGHTPAINT,
    "paint": I.WEIGHTPAINT,
    "creature": I.CAT_CREATURE,
    "character": I.CAT_CHARACTER,
    "item": I.CAT_ITEM,
    "item/armor": I.CAT_ITEM,
    "module": I.CAT_MODULE,
    "other": I.CAT_OTHER,
    "all": I.LIBRARY,
    "logo": I.LOGO,
}


def get(name: str, size: int = 16) -> QtGui.QIcon:
    key = f"{name}_{size}"
    if key in _cache:
        return _cache[key]
    path = ICONS_DIR / f"{name}.svg"
    if path.exists():
        icon = QtGui.QIcon(str(path))
        _cache[key] = icon
        return icon
    path = ICONS_DIR / f"{name}_{size}.png"
    if not path.exists():
        path = ICONS_DIR / f"{name}_24.png"
    icon = QtGui.QIcon(str(path)) if path.exists() else QtGui.QIcon()
    _cache[key] = icon
    return icon


def pixmap(name: str, size: int = 16) -> QtGui.QPixmap:
    return get(name, size).pixmap(size, size)


def icon_for_label(label: str, size: int = 16) -> QtGui.QIcon:
    raw = label.strip()
    i = 0
    while i < len(raw):
        cat = unicodedata.category(raw[i])
        if cat.startswith("S") or cat.startswith("C") or raw[i].isspace():
            i += 1
        else:
            break
    key = raw[i:].lower().strip()
    best_icon: Optional[str] = None
    best_len = 0
    for pattern, icon_name in LABEL_TO_ICON.items():
        if key.startswith(pattern) and len(pattern) > best_len:
            best_icon = icon_name
            best_len = len(pattern)
    return get(best_icon, size) if best_icon else QtGui.QIcon()


def action_icon_kwargs(label: str, size: int = 16) -> dict:
    icon = icon_for_label(label, size)
    return {"icon": icon} if not icon.isNull() else {}

