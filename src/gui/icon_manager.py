# ─────────────────────────────────────────────────────────────────────────────
#  ⚠  FROZEN — LEGACY TKINTER MODULE  ⚠
# ─────────────────────────────────────────────────────────────────────────────
#  This file is part of the pre-Qt GhostRigger UI and is kept ONLY as a
#  read-only reference until milestone M3 (T302) deletes it.
#
#  Do NOT add new features here.  Do NOT touch business logic here.
#  All active UI work happens under qt_*.py in this package.
#
#  Tracking: knowledge_base/roadmap/02_roadmap_2026_05.md  (M0/T004, M3/T302)
# ─────────────────────────────────────────────────────────────────────────────
"""
src/gui/icon_manager.py
=======================
KotOR-style icon manager for the GhostRigger UI.

Loads pre-rendered 16×16 and 24×24 PNG icons from src/gui/icons/ and
exposes them as Tkinter PhotoImage objects that can be used in buttons,
notebook tabs, and labels.

Usage
-----
    from src.gui.icon_manager import Icons

    # In any widget code:
    btn = tk.Button(parent, image=Icons.get("open"), compound="left", text=" Open")
    tab_nb.add(frame, image=Icons.get("library", 16), compound="left", text=" Library")

Icons.get(name, size=16) returns a PhotoImage (cached) or None on failure.
Icons.label_kwargs(name, text, size=16) returns a dict suitable for **kwargs
on tk.Label / tk.Button with image + compound + text pre-filled.
"""

import os
import tkinter as tk
from pathlib import Path
from typing import Optional

# Absolute path to the icons directory
_ICONS_DIR = Path(__file__).parent / "icons"

# ── Singleton cache ─────────────────────────────────────────────────────────
_cache: dict[str, "tk.PhotoImage"] = {}
_tk_root: Optional[tk.Misc] = None  # must be set before first load


def init(root: tk.Misc) -> None:
    """Call once after the Tk root window is created."""
    global _tk_root
    _tk_root = root


def get(name: str, size: int = 16) -> Optional["tk.PhotoImage"]:
    """
    Return a cached PhotoImage for *name* at *size* (16 or 24).
    Returns None if the PNG file is missing or Tkinter is unavailable.
    """
    key = f"{name}_{size}"
    if key in _cache:
        return _cache[key]

    path = _ICONS_DIR / f"{name}_{size}.png"
    if not path.exists():
        return None

    try:
        img = tk.PhotoImage(file=str(path), master=_tk_root)
        _cache[key] = img
        return img
    except Exception:
        return None


def label_kwargs(name: str, text: str = "", size: int = 16) -> dict:
    """
    Return kwargs for a tk.Button / tk.Label that shows an icon + label text.
    Falls back to text-only if the icon is unavailable.

    Example
    -------
        btn = tk.Button(parent, **Icons.label_kwargs("open", " Open"))
    """
    img = get(name, size)
    if img is not None:
        return {"image": img, "compound": "left", "text": text}
    return {"text": text.strip()}  # fallback: strip leading space


def tab_kwargs(name: str, text: str = "", size: int = 16) -> dict:
    """
    Return kwargs for ttk.Notebook.add() that shows an icon + tab label.
    Falls back to text-only.
    """
    img = get(name, size)
    if img is not None:
        return {"image": img, "compound": "left", "text": text}
    return {"text": text.strip()}


# ── Convenience names (avoid typos at call sites) ───────────────────────────
class I:
    """Shorthand constants – use as Icons.I.OPEN etc."""
    OPEN        = "open"
    IMPORT      = "import"
    EXPORT      = "export"
    AUTORIG     = "autorig"
    SETTINGS    = "settings"
    REFRESH     = "refresh"
    CLOTH       = "cloth"
    MODULAR     = "modular"
    DIAG        = "diag"
    TEXTURE     = "texture"
    LIBRARY     = "library"
    SEARCH      = "search"
    SKELETON    = "skeleton"
    PROPS       = "props"
    ANIMS       = "anims"
    RIG         = "rig"
    NORMALMAP   = "normalmap"
    RESOURCES   = "resources"
    TWODA       = "twoda"
    LOGO        = "logo"
    CLOSE       = "close"
    LOADMODEL   = "loadmodel"
    WEIGHTPAINT  = "weightpaint"
    # Character Builder icons
    CHARBUILDER  = "charbuilder"
    TEMPLATE     = "template"
    SELECTALL    = "selectall"
    HEAD         = "head"
    BODY         = "body"
    # Category icons
    CAT_CREATURE  = "cat_creature"
    CAT_CHARACTER = "cat_character"
    CAT_ITEM      = "cat_item"
    CAT_MODULE    = "cat_module"
    CAT_OTHER     = "cat_other"


# ── Mapping: emoji/text label → icon name ────────────────────────────────────
# Used by _btn_icon() helper to auto-detect which icon to use.
LABEL_TO_ICON: dict[str, str] = {
    # toolbar buttons
    "open":         I.OPEN,
    "import":       I.IMPORT,
    "export":       I.EXPORT,
    "auto-rig":     I.AUTORIG,
    "autorig":      I.AUTORIG,
    "rig":          I.RIG,
    "settings":     I.SETTINGS,
    "refresh":      I.REFRESH,
    "cloth":        I.CLOTH,
    "modular":      I.MODULAR,
    "diag":         I.DIAG,
    "tex":          I.TEXTURE,
    "texture":      I.TEXTURE,
    # left-panel tabs
    "library":      I.LIBRARY,
    "nodes":        I.SKELETON,
    "skeleton":     I.SKELETON,
    "2da":          I.TWODA,
    "2das":         I.TWODA,
    "resources":    I.RESOURCES,
    # right-panel tabs
    "props":        I.PROPS,
    "anims":        I.ANIMS,
    "anim":         I.ANIMS,
    "normalmap":    I.NORMALMAP,
    "normmap":      I.NORMALMAP,
    # library panel controls
    "search":           I.SEARCH,
    "load":             I.LOADMODEL,
    "load model":       I.LOADMODEL,
    "extract":          I.OPEN,
    "close":            I.CLOSE,
    "clear":            I.CLOSE,
    "scan":             I.REFRESH,
    "deep scan":        I.REFRESH,
    "auto-detect":      I.SEARCH,
    "batch obj":        I.EXPORT,
    "batch ascii":      I.EXPORT,
    "batch tga":        I.TEXTURE,
    "copy":             I.PROPS,
    "save":             I.OPEN,
    "import json":      I.IMPORT,
    # rig panel tabs
    "auto":             I.AUTORIG,
    "auto-rig":         I.AUTORIG,
    "auto-rig model":   I.AUTORIG,
    "grig":             I.SKELETON,
    "generate skeleton":I.SKELETON,
    "manual":           I.SKELETON,
    "accurig":          I.RIG,
    "full acurig":      I.RIG,
    "weight":           I.WEIGHTPAINT,
    "weightpaint":      I.WEIGHTPAINT,
    "weight preview":   I.WEIGHTPAINT,
    "paint":            I.WEIGHTPAINT,
    "paint sphere":     I.WEIGHTPAINT,
    "paint / apply":    I.WEIGHTPAINT,
    "map fbx":          I.RIG,
    "snap":             I.SKELETON,
    "heat-map":         I.WEIGHTPAINT,
    "normalize":        I.WEIGHTPAINT,
    "prune":            I.CLOSE,
    "clear mesh":       I.CLOSE,
    "flood":            I.WEIGHTPAINT,
    "inspect":          I.DIAG,
    "bake":             I.NORMALMAP,
    "bake normal":      I.NORMALMAP,
    "parent":           I.SKELETON,
    "build chain":      I.SKELETON,
    "insert bone":      I.SKELETON,
    "mirror":           I.REFRESH,
    "refresh":          I.REFRESH,
    "refresh list":     I.REFRESH,
    "refresh lists":    I.REFRESH,
    "remove":           I.CLOSE,
    "modular mode":     I.MODULAR,
    # Character Builder
    "character builder": I.CHARBUILDER,
    "charbuilder":       I.CHARBUILDER,
    "template":          I.TEMPLATE,
    "load template":     I.TEMPLATE,
    "body template":     I.BODY,
    "head template":     I.HEAD,
    "select all":        I.SELECTALL,
    "select all bones":  I.SELECTALL,
    "body":              I.BODY,
    "head":              I.HEAD,
    "load body":         I.BODY,
    "load head":         I.HEAD,
    "t-pose":           I.AUTORIG,
    "a-pose":           I.AUTORIG,
    "compute":          I.DIAG,
    "stats":            I.DIAG,
    "lock":             I.PROPS,
    "unlock":           I.PROPS,
    "delete":           I.CLOSE,
    "clear overlay":    I.CLOSE,
    "auto-place":       I.SKELETON,
    "snap to":          I.SKELETON,
    "auto-skin":        I.WEIGHTPAINT,
    "export":           I.EXPORT,
    # category tabs
    "creature":         I.CAT_CREATURE,
    "character":        I.CAT_CHARACTER,
    "item":             I.CAT_ITEM,
    "item/armor":       I.CAT_ITEM,
    "module":           I.CAT_MODULE,
    "other":            I.CAT_OTHER,
    "all":              I.LIBRARY,
    "logo":             I.LOGO,
}


def icon_for_label(label: str, size: int = 16) -> Optional["tk.PhotoImage"]:
    """Fuzzy-match a button label to an icon name and return the PhotoImage.

    Strips leading whitespace and common emoji prefixes, then checks the
    LABEL_TO_ICON map for a prefix match.  Returns None on no match so the
    button gracefully falls back to text-only.
    """
    # Strip whitespace and any stray unicode symbols
    import unicodedata
    raw = label.strip()
    # Drop leading emoji / symbol characters (categories So, Sm, Sk, Cs)
    i = 0
    while i < len(raw):
        cat = unicodedata.category(raw[i])
        if cat.startswith('S') or cat.startswith('C') or raw[i] == ' ':
            i += 1
        else:
            break
    key = raw[i:].lower().strip()
    if not key:
        return None
    # Longest-prefix-first match
    best_icon = None
    best_len  = 0
    for pattern, icon_name in LABEL_TO_ICON.items():
        if key.startswith(pattern) and len(pattern) > best_len:
            best_icon = icon_name
            best_len  = len(pattern)
    if best_icon:
        return get(best_icon, size)
    return None
