"""
game_detector.py
================
Auto-detects KotOR 1 and KotOR 2 installation directories on the host system.

Supports:
  - Steam  (Windows, macOS, Linux — reads libraryfolders.vdf)
  - GOG Galaxy (Windows registry + common install paths)
  - Default LucasArts install paths (Windows C:/Program Files, etc.)
  - macOS App Store / direct install paths
  - Linux / Steam Deck (Proton prefix, ~/.local/share/Steam)
  - WINE prefix on Linux
  - Environment variables:  KOTOR1_DIR, KOTOR2_DIR
  - Stored config  (~/.ghostrigger/config.json)

Usage
-----
    from src.resources.game_detector import detect_kotor_dirs, save_config, load_config

    k1, k2 = detect_kotor_dirs()   # returns (str|None, str|None)
    if k1:
        print(f"KotOR 1 found at: {k1}")
    if k2:
        print(f"KotOR 2 found at: {k2}")

    # Save user-confirmed dirs for future sessions
    save_config(k1, k2)
"""

from __future__ import annotations

import os
import sys
import json
import logging
from pathlib import Path
from typing import Optional, Tuple, List

log = logging.getLogger(__name__)

# ── Steam App IDs ─────────────────────────────────────────────────────────────
_STEAM_APPID_K1 = "32470"    # Star Wars: Knights of the Old Republic
_STEAM_APPID_K2 = "208580"   # Star Wars: Knights of the Old Republic II

# ── Marker files that prove a directory is a KotOR installation ───────────────
_K1_MARKERS = ["chitin.key", "swkotor.exe", "swkotor"]
_K2_MARKERS = ["chitin.key", "swkotor2.exe", "swkotor2"]
_EITHER_MARKERS = ["chitin.key"]

# ── Config file ───────────────────────────────────────────────────────────────
_CONFIG_PATH = Path.home() / ".ghostrigger" / "config.json"


# ──────────────────────────────────────────────────────────────────────────────
# Public API
# ──────────────────────────────────────────────────────────────────────────────

def detect_kotor_dirs(
    prefer_config: bool = True,
) -> Tuple[Optional[str], Optional[str]]:
    """
    Auto-detect KotOR 1 and KotOR 2 installation directories.

    Returns
    -------
    (k1_dir, k2_dir) — either may be None if not found.
    """
    k1: Optional[str] = None
    k2: Optional[str] = None

    # 1. Stored config (fastest, user-confirmed)
    if prefer_config:
        k1c, k2c = load_config()
        if k1c and _is_kotor_dir(k1c, game=1):
            k1 = k1c
        if k2c and _is_kotor_dir(k2c, game=2):
            k2 = k2c
        if k1 and k2:
            log.info("Both KotOR dirs loaded from saved config.")
            return k1, k2

    # 2. Environment variables
    env_k1 = os.environ.get("KOTOR1_DIR", "")
    env_k2 = os.environ.get("KOTOR2_DIR", "")
    if env_k1 and _is_kotor_dir(env_k1, game=1):
        k1 = k1 or env_k1
    if env_k2 and _is_kotor_dir(env_k2, game=2):
        k2 = k2 or env_k2
    if k1 and k2:
        log.info("Both KotOR dirs found via environment variables.")
        return k1, k2

    # 3. Steam
    for path in _steam_candidates():
        if not k1 and _is_kotor_dir(path, game=1):
            k1 = str(path)
            log.info(f"KotOR 1 found via Steam: {k1}")
        elif not k2 and _is_kotor_dir(path, game=2):
            k2 = str(path)
            log.info(f"KotOR 2 found via Steam: {k2}")
        if k1 and k2:
            break

    # 4. GOG
    for path in _gog_candidates():
        if not k1 and _is_kotor_dir(path, game=1):
            k1 = str(path)
            log.info(f"KotOR 1 found via GOG: {k1}")
        elif not k2 and _is_kotor_dir(path, game=2):
            k2 = str(path)
            log.info(f"KotOR 2 found via GOG: {k2}")
        if k1 and k2:
            break

    # 5. Platform-specific default paths
    for path in _default_candidates():
        if not k1 and _is_kotor_dir(path, game=1):
            k1 = str(path)
            log.info(f"KotOR 1 found at default path: {k1}")
        elif not k2 and _is_kotor_dir(path, game=2):
            k2 = str(path)
            log.info(f"KotOR 2 found at default path: {k2}")
        if k1 and k2:
            break

    # 6. Fallback: project-local game_data (developer convenience)
    local_k1 = Path(__file__).parent.parent.parent / "game_data" / "k1_extracted"
    local_k2 = Path(__file__).parent.parent.parent / "game_data" / "k2_extracted"
    if not k1 and local_k1.is_dir() and (local_k1 / "chitin.key").exists():
        k1 = str(local_k1)
        log.info(f"KotOR 1 found in project game_data: {k1}")
    if not k2 and local_k2.is_dir() and (local_k2 / "chitin.key").exists():
        k2 = str(local_k2)
        log.info(f"KotOR 2 found in project game_data: {k2}")

    return k1, k2


def save_config(k1_dir: Optional[str], k2_dir: Optional[str]) -> None:
    """Persist discovered or user-selected paths to ~/.ghostrigger/config.json."""
    _CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    cfg: dict = {}
    if _CONFIG_PATH.exists():
        try:
            with open(_CONFIG_PATH) as f:
                cfg = json.load(f)
        except Exception:
            pass
    if k1_dir is not None:
        cfg["k1_dir"] = str(k1_dir)
    if k2_dir is not None:
        cfg["k2_dir"] = str(k2_dir)
    with open(_CONFIG_PATH, "w") as f:
        json.dump(cfg, f, indent=2)
    log.info(f"Config saved to {_CONFIG_PATH}")


def load_config() -> Tuple[Optional[str], Optional[str]]:
    """Load paths from ~/.ghostrigger/config.json."""
    if not _CONFIG_PATH.exists():
        return None, None
    try:
        with open(_CONFIG_PATH) as f:
            cfg = json.load(f)
        return cfg.get("k1_dir"), cfg.get("k2_dir")
    except Exception as e:
        log.debug(f"Failed to load config: {e}")
        return None, None


def list_all_candidates() -> List[dict]:
    """
    Return a list of all candidate paths with their detection status.
    Useful for the 'Browse for Game Directory' dialog.
    """
    results = []
    for path in _steam_candidates():
        p = Path(path)
        results.append({
            "source": "Steam",
            "path": str(p),
            "exists": p.is_dir(),
            "is_k1": _is_kotor_dir(p, game=1),
            "is_k2": _is_kotor_dir(p, game=2),
        })
    for path in _gog_candidates():
        p = Path(path)
        results.append({
            "source": "GOG",
            "path": str(p),
            "exists": p.is_dir(),
            "is_k1": _is_kotor_dir(p, game=1),
            "is_k2": _is_kotor_dir(p, game=2),
        })
    for path in _default_candidates():
        p = Path(path)
        results.append({
            "source": "Default",
            "path": str(p),
            "exists": p.is_dir(),
            "is_k1": _is_kotor_dir(p, game=1),
            "is_k2": _is_kotor_dir(p, game=2),
        })
    return results


# ──────────────────────────────────────────────────────────────────────────────
# Internal helpers
# ──────────────────────────────────────────────────────────────────────────────

def _is_kotor_dir(path, game: int = 0) -> bool:
    """
    Return True if *path* looks like a KotOR installation directory.

    game=0 — accept either K1 or K2
    game=1 — must be KotOR 1
    game=2 — must be KotOR 2
    """
    p = Path(path)
    if not p.is_dir():
        return False
    has_key = (p / "chitin.key").exists()
    if not has_key:
        return False

    if game == 1:
        # K1 marker: swkotor.exe (Windows) or swkotor (Linux/Mac)
        # Or: modules/ directory containing m01aa*.mod
        has_exe = (p / "swkotor.exe").exists() or (p / "swkotor").exists()
        has_mods = (p / "modules").is_dir()
        if has_exe:
            return True
        if has_mods:
            # Check for K1-specific module names
            mods = p / "modules"
            for f in mods.iterdir() if mods.exists() else []:
                if f.name.lower().startswith("m01aa"):
                    return True
        # Fallback: check if 'lips' folder has k1 lines (tar_hk.mod etc.)
        return False

    elif game == 2:
        has_exe = (p / "swkotor2.exe").exists() or (p / "swkotor2").exists()
        has_mods = (p / "modules").is_dir()
        if has_exe:
            return True
        if has_mods:
            mods = p / "modules"
            for f in mods.iterdir() if mods.exists() else []:
                if f.name.lower().startswith("101per"):
                    return True
        return False

    else:
        # Accept either
        return True


def _steam_library_paths() -> List[Path]:
    """Find all Steam library folders on the system."""
    libraries: List[Path] = []

    # Platform-specific Steam root
    steam_roots: List[Path] = []
    if sys.platform == "win32":
        steam_roots += [
            Path(os.environ.get("ProgramFiles(x86)", "C:/Program Files (x86)")) / "Steam",
            Path(os.environ.get("ProgramFiles", "C:/Program Files")) / "Steam",
            Path("C:/Steam"),
        ]
    elif sys.platform == "darwin":
        steam_roots += [
            Path.home() / "Library" / "Application Support" / "Steam",
        ]
    else:  # Linux / Steam Deck
        steam_roots += [
            Path.home() / ".steam" / "steam",
            Path.home() / ".steam" / "root",
            Path.home() / ".local" / "share" / "Steam",
            Path("/run/media") / os.environ.get("USER", "user") / ".steam" / "steam",
            # Steam Deck
            Path("/home/deck/.steam/steam"),
            Path("/home/deck/.local/share/Steam"),
        ]

    for root in steam_roots:
        if not root.is_dir():
            continue
        libraries.append(root / "steamapps")

        # Read libraryfolders.vdf for additional library paths
        vdf = root / "steamapps" / "libraryfolders.vdf"
        if not vdf.exists():
            vdf = root / "config" / "libraryfolders.vdf"
        if vdf.exists():
            try:
                text = vdf.read_text(errors="replace")
                # Parse "path" entries from VDF (simple regex-style)
                import re
                for m in re.finditer(r'"path"\s+"([^"]+)"', text):
                    lib_path = Path(m.group(1).replace("\\\\", "/"))
                    sa = lib_path / "steamapps"
                    if sa.is_dir():
                        libraries.append(sa)
            except Exception as e:
                log.debug(f"Failed to parse {vdf}: {e}")

    return libraries


def _steam_candidates() -> List[Path]:
    """Return candidate paths for KotOR via Steam."""
    candidates: List[Path] = []
    for lib in _steam_library_paths():
        # Common install names
        candidates += [
            lib / "common" / "Knights of the Old Republic",
            lib / "common" / "Knights of the Old Republic II",
            lib / "common" / "swkotor",
            lib / "common" / "swkotor2",
            # Steam Deck / Proton
            lib / "common" / "Knights of the Old Republic" / "pfx" / "drive_c" / "Program Files (x86)" / "LucasArts" / "SWKotOR",
        ]
        # Read acf manifest files for exact paths
        for appid in [_STEAM_APPID_K1, _STEAM_APPID_K2]:
            acf = lib / f"appmanifest_{appid}.acf"
            if acf.exists():
                try:
                    text = acf.read_text(errors="replace")
                    import re
                    m = re.search(r'"installdir"\s+"([^"]+)"', text)
                    if m:
                        install_dir = lib / "common" / m.group(1)
                        candidates.append(install_dir)
                except Exception:
                    pass

    # Proton / Wine prefix locations on Linux
    if sys.platform not in ("win32", "darwin"):
        wine_roots = [
            Path.home() / ".wine" / "drive_c",
            Path.home() / ".local" / "share" / "Steam" / "steamapps" / "compatdata" / _STEAM_APPID_K1 / "pfx" / "drive_c",
            Path.home() / ".local" / "share" / "Steam" / "steamapps" / "compatdata" / _STEAM_APPID_K2 / "pfx" / "drive_c",
        ]
        for wine_c in wine_roots:
            candidates += [
                wine_c / "Program Files (x86)" / "LucasArts" / "SWKotOR",
                wine_c / "Program Files (x86)" / "LucasArts" / "SWKotOR2",
                wine_c / "Program Files" / "LucasArts" / "SWKotOR",
                wine_c / "Program Files" / "LucasArts" / "SWKotOR2",
            ]

    return candidates


def _gog_candidates() -> List[Path]:
    """Return candidate paths for KotOR via GOG Galaxy."""
    candidates: List[Path] = []

    if sys.platform == "win32":
        # Try Windows registry (GOG stores install paths there)
        try:
            import winreg
            gog_keys = [
                r"SOFTWARE\WOW6432Node\GOG.com\Games\1207666283",  # K1
                r"SOFTWARE\WOW6432Node\GOG.com\Games\1207666893",  # K2
                r"SOFTWARE\GOG.com\Games\1207666283",
                r"SOFTWARE\GOG.com\Games\1207666893",
            ]
            for key_path in gog_keys:
                try:
                    key = winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, key_path)
                    path_val, _ = winreg.QueryValueEx(key, "PATH")
                    if path_val:
                        candidates.append(Path(path_val))
                    winreg.CloseKey(key)
                except OSError:
                    pass
        except ImportError:
            pass  # Not Windows

        # Common GOG install locations
        for base in [
            "C:/GOG Games",
            "D:/GOG Games",
            os.environ.get("ProgramFiles(x86)", "C:/Program Files (x86)") + "/GOG Galaxy/Games",
            os.environ.get("ProgramFiles", "C:/Program Files") + "/GOG Galaxy/Games",
        ]:
            candidates += [
                Path(base) / "Star Wars - KotOR",
                Path(base) / "Star Wars - KotOR 2",
                Path(base) / "Star Wars KotOR",
                Path(base) / "Star Wars KotOR II",
                Path(base) / "Knights of the Old Republic",
                Path(base) / "Knights of the Old Republic II",
            ]

    elif sys.platform == "darwin":
        candidates += [
            Path.home() / "Applications" / "Star Wars- Knights of the Old Republic.app" / "Contents" / "Resources" / "game",
            Path.home() / "Applications" / "Star Wars- Knights of the Old Republic II.app" / "Contents" / "Resources" / "game",
            Path("/Applications") / "Star Wars- Knights of the Old Republic.app" / "Contents" / "Resources" / "game",
        ]

    return candidates


def _default_candidates() -> List[Path]:
    """Return default / common installation paths."""
    candidates: List[Path] = []

    if sys.platform == "win32":
        pf86 = os.environ.get("ProgramFiles(x86)", "C:/Program Files (x86)")
        pf = os.environ.get("ProgramFiles", "C:/Program Files")
        for base in [pf86, pf, "C:", "D:", "E:"]:
            candidates += [
                Path(base) / "LucasArts" / "SWKotOR",
                Path(base) / "LucasArts" / "SWKotOR2",
                Path(base) / "Steam" / "steamapps" / "common" / "Knights of the Old Republic",
                Path(base) / "Steam" / "steamapps" / "common" / "Knights of the Old Republic II",
            ]

    elif sys.platform == "darwin":
        candidates += [
            Path.home() / "Library" / "Application Support" / "Steam" / "steamapps" / "common" / "Knights of the Old Republic",
            Path.home() / "Library" / "Application Support" / "Steam" / "steamapps" / "common" / "Knights of the Old Republic II",
            # Mac App Store / direct installs
            Path("/Applications") / "Star Wars Knights of the Old Republic.app" / "Contents" / "Resources",
            Path("/Applications") / "Knights of the Old Republic.app" / "Contents" / "MacOS",
        ]

    else:  # Linux
        candidates += [
            Path.home() / ".local" / "share" / "Steam" / "steamapps" / "common" / "Knights of the Old Republic",
            Path.home() / ".local" / "share" / "Steam" / "steamapps" / "common" / "Knights of the Old Republic II",
            Path("/opt/kotor"),
            Path("/opt/kotor2"),
            Path("/usr/local/games/kotor"),
            Path("/usr/local/games/kotor2"),
            # Lutris
            Path.home() / "Games" / "kotor",
            Path.home() / "Games" / "kotor2",
            Path.home() / "Games" / "star-wars-kotor",
            Path.home() / "Games" / "star-wars-kotor-ii",
        ]

    return candidates


# ──────────────────────────────────────────────────────────────────────────────
# CLI entry point (for testing)
# ──────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    logging.basicConfig(level=logging.DEBUG)
    print("Detecting KotOR directories...\n")
    k1, k2 = detect_kotor_dirs()
    print(f"KotOR 1: {k1 or '(not found)'}")
    print(f"KotOR 2: {k2 or '(not found)'}")
    print()

    print("All candidates:")
    for c in list_all_candidates():
        status = "✓ K1" if c["is_k1"] else ("✓ K2" if c["is_k2"] else ("exists" if c["exists"] else "—"))
        print(f"  [{c['source']:7}] {status:8} {c['path']}")
