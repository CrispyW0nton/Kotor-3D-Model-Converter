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

from src.gui.libtheme.icon_manager import ThemeIconManager


ICONS_DIR = Path(__file__).resolve().parents[1] / "icons"
_cache: dict[str, QtGui.QIcon] = {}
_fallback_icons = ThemeIconManager(ICONS_DIR)


class I:
    SCENE = "scene"
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
    MODULE_MESHES = "module_meshes"
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
    CAMERA_FREE = "camera_free"
    CAMERA_TARGET = "camera_target"
    CAMERA_CINEMATIC = "camera_cinematic"
    VIEWPORT_SELECT_CAMERAS = "viewport_select_cameras"
    VIEWPORT_LOCK_CAMERA = "viewport_lock_camera"
    LIGHT_POINT = "light_point"
    LIGHT_SPOT = "light_spot"
    LIGHT_DIRECTIONAL = "light_directional"
    LIGHT_AREA = "light_area"
    LIGHT_AMBIENT = "light_ambient"
    VIEWPORT_LIGHT_HELPERS = "viewport_light_helpers"
    LIGHTING_MODE_SCENE = "lighting_mode_scene"
    LIGHTING_MODE_UNLIT = "lighting_mode_unlit"
    LIGHTING_MODE_FULLBRIGHT = "lighting_mode_fullbright"
    LIGHTING_MODE_LIGHTMAP = "lighting_mode_lightmap"
    LIGHTING_MODE_DIFFUSE = "lighting_mode_diffuse"
    LIGHTING_MODE_NORMAL = "lighting_mode_normal"
    LIGHTING_MODE_SPECULAR = "lighting_mode_specular"
    LIGHTING_MODE_ENVIRONMENT = "lighting_mode_environment"
    LIGHTING_MODE_SHADER = "lighting_mode_shader"
    LIGHTING_MODE_PHOTOREAL = "lighting_mode_photoreal"
    LIGHTING_COMPLEXITY_OFF = "lighting_complexity_off"
    LIGHTING_COMPLEXITY_BASIC = "lighting_complexity_basic"
    LIGHTING_COMPLEXITY_OVERDRAW = "lighting_complexity_overdraw"
    LIGHTING_COMPLEXITY_TEXTURE = "lighting_complexity_texture"
    LIGHTING_COMPLEXITY_LIGHTING = "lighting_complexity_lighting"
    LIGHTING_COMPLEXITY_FULL = "lighting_complexity_full"
    LIGHTING_RIG_NONE = "lighting_rig_none"
    LIGHTING_RIG_KOTOR = "lighting_rig_kotor"
    LIGHTING_RIG_NEUTRAL = "lighting_rig_neutral"
    LIGHTING_RIG_WARM = "lighting_rig_warm"
    LIGHTING_RIG_COLD = "lighting_rig_cold"
    LIGHTING_RIG_TORCH = "lighting_rig_torch"
    LIGHTING_RIG_MOON = "lighting_rig_moon"
    LIGHTING_RIG_SOFTBOX = "lighting_rig_softbox"
    LIGHTING_RIG_UNREAL = "lighting_rig_unreal"
    LIGHTING_RIG_MAX = "lighting_rig_max"
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
    "module meshes": I.MODULE_MESHES,
    "module_meshes": I.MODULE_MESHES,
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
    "free camera": I.CAMERA_FREE,
    "target camera": I.CAMERA_TARGET,
    "cinematic camera": I.CAMERA_CINEMATIC,
    "point light": I.LIGHT_POINT,
    "spot light": I.LIGHT_SPOT,
    "directional light": I.LIGHT_DIRECTIONAL,
    "area light": I.LIGHT_AREA,
    "ambient light": I.LIGHT_AMBIENT,
    "light helpers": I.VIEWPORT_LIGHT_HELPERS,
    "scene lit": I.LIGHTING_MODE_SCENE,
    "unlit": I.LIGHTING_MODE_UNLIT,
    "fullbright": I.LIGHTING_MODE_FULLBRIGHT,
    "lightmap preview": I.LIGHTING_MODE_LIGHTMAP,
    "diffuse only": I.LIGHTING_MODE_DIFFUSE,
    "normal only": I.LIGHTING_MODE_NORMAL,
    "specular only": I.LIGHTING_MODE_SPECULAR,
    "environment only": I.LIGHTING_MODE_ENVIRONMENT,
    "shader complexity": I.LIGHTING_MODE_SHADER,
    "photoreal preview": I.LIGHTING_MODE_PHOTOREAL,
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
    icon = QtGui.QIcon(str(path)) if path.exists() else _fallback_icons.icon(name, None, size)
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
    return get(best_icon, size) if best_icon else _fallback_icons.icon(key, None, size)


def action_icon_kwargs(label: str, size: int = 16) -> dict:
    icon = icon_for_label(label, size)
    return {"icon": icon} if not icon.isNull() else {}

