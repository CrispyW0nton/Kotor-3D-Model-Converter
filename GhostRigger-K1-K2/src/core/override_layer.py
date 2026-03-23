"""
Override Layer  –  Phase 12.1
==============================
Override-folder resource layer for GhostRigger.

Scans a KotOR game's Override/ directory and provides an override-aware
resource lookup that sits in front of the main GameLibrary (KEY/BIF/ERF).

When a resource is present in the Override/ folder it takes precedence
over the game archive copy, exactly as the KotOR engine itself does.

Reference: PyKotor/extract/installation.py → Installation.load_override()
           KotOR engine: all loose files in Override/ loaded before BIFs.

Usage
-----
::

    from src.core.override_layer import OverrideLayer

    ol = OverrideLayer(game_dir='/path/to/KotOR')
    ol.scan()                           # index Override/ files

    mdl_bytes = ol.get('pfh0', 'mdl')  # returns bytes or None
    mdx_bytes = ol.get('pfh0', 'mdx')  # companion MDX
    all_mdl   = ol.list_by_ext('mdl')  # all overridden MDL resrefs

    # Check if a resource is overridden
    if ol.has('pfh0', 'mdl'):
        print('[Override] pfh0.mdl is overridden')

    # Merge with main library: try override first
    from src.resources.game_library import GameLibrary
    lib = GameLibrary(); lib.load_game(game_dir, game='K1')
    data = ol.get('pfh0', 'mdl') or lib.get_model('pfh0')

Supported file extensions
--------------------------
  MDL/MDX   models (primary use-case)
  TPC/TGA   textures
  2DA        data tables
  MDX        vertex data
  UTC/UTI/UTP/UTD/UTE/UTS  GFF templates
  ARE/IFO/GIT/LYT/VIS       module files
  WOK/PWK/DWK               walkmesh files
  NCS/NSS                   scripts
  Any other extension is indexed as-is.

Override badge
--------------
``OverrideLayer.badge(resref, ext)`` returns '[Override]' if the resource
is overridden, '' otherwise.  Used by the UI to display the badge.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path
from typing import Dict, List, Optional, Set

log = logging.getLogger(__name__)

# File extensions that GhostRigger cares about (lowercase, no dot)
_KNOWN_EXTS: Set[str] = {
    'mdl', 'mdx', 'tpc', 'tga', '2da', 'txb', 'txi',
    'utc', 'uti', 'utp', 'utd', 'ute', 'uts', 'utm',
    'are', 'ifo', 'git', 'lyt', 'vis', 'wok', 'pwk', 'dwk',
    'ncs', 'nss', 'dlg', 'jrl', 'tlk', 'ssf',
}


class OverrideEntry:
    """Metadata for a single file in the Override/ folder."""

    __slots__ = ('resref', 'ext', 'path')

    def __init__(self, resref: str, ext: str, path: Path):
        self.resref = resref      # lower-case stem, e.g. 'pfh0'
        self.ext    = ext         # lower-case extension, e.g. 'mdl'
        self.path   = path        # absolute Path object


class OverrideLayer:
    """
    Index of all files in a KotOR Override/ directory.

    Override lookups are O(1) via a {(resref, ext) → OverrideEntry} dict.
    The scan is lazy — call scan() explicitly or pass auto_scan=True.
    """

    def __init__(self, game_dir: str, auto_scan: bool = False):
        """
        Parameters
        ----------
        game_dir : str
            Root of the KotOR installation (the folder containing chitin.key).
        auto_scan : bool
            If True, call scan() immediately on construction.
        """
        self._game_dir = Path(game_dir)
        self._override_dir = self._game_dir / 'Override'
        self._index: Dict[tuple, OverrideEntry] = {}   # (resref, ext) → entry
        self._scanned = False

        if auto_scan:
            self.scan()

    # ─────────────────────────────  Public API  ─────────────────────────────

    @property
    def game_dir(self) -> Path:
        return self._game_dir

    @property
    def override_dir(self) -> Path:
        return self._override_dir

    @property
    def is_available(self) -> bool:
        """True if the Override/ directory exists."""
        return self._override_dir.exists() and self._override_dir.is_dir()

    @property
    def entry_count(self) -> int:
        """Number of indexed override entries."""
        return len(self._index)

    def scan(self) -> int:
        """
        Scan Override/ and index all files.

        Returns the number of files indexed.
        Uses non-recursive scan (Override/ is flat in KotOR).
        Skips directories and hidden files.
        """
        self._index.clear()
        count = 0

        if not self.is_available:
            log.debug(f'OverrideLayer.scan: no Override/ dir at {self._override_dir}')
            self._scanned = True
            return 0

        try:
            for p in self._override_dir.iterdir():
                if not p.is_file():
                    continue
                if p.name.startswith('.'):
                    continue
                resref = p.stem.lower()
                ext    = p.suffix.lstrip('.').lower()
                if not resref:
                    continue
                entry = OverrideEntry(resref=resref, ext=ext, path=p)
                self._index[(resref, ext)] = entry
                count += 1
        except PermissionError as e:
            log.warning(f'OverrideLayer.scan: permission error scanning {self._override_dir}: {e}')

        self._scanned = True
        log.debug(f'OverrideLayer: scanned {count} override files in {self._override_dir}')
        return count

    def has(self, resref: str, ext: str) -> bool:
        """Return True if (resref, ext) is present in Override/."""
        return (resref.lower(), ext.lower()) in self._index

    def get(self, resref: str, ext: str) -> Optional[bytes]:
        """
        Return file bytes for (resref, ext) from Override/, or None.

        Reads the file on every call (no in-memory caching by design —
        KotOR files are large and the caller may have its own cache).
        """
        entry = self._index.get((resref.lower(), ext.lower()))
        if entry is None:
            return None
        try:
            return entry.path.read_bytes()
        except OSError as e:
            log.warning(f'OverrideLayer.get: failed to read {entry.path}: {e}')
            return None

    def get_path(self, resref: str, ext: str) -> Optional[Path]:
        """Return the Path for (resref, ext), or None if not overridden."""
        entry = self._index.get((resref.lower(), ext.lower()))
        return entry.path if entry else None

    def list_by_ext(self, ext: str) -> List[str]:
        """Return sorted list of resrefs overriding files with given extension."""
        ext = ext.lower()
        return sorted(k[0] for k in self._index if k[1] == ext)

    def list_all(self) -> List[OverrideEntry]:
        """Return all override entries sorted by (ext, resref)."""
        return sorted(self._index.values(), key=lambda e: (e.ext, e.resref))

    def badge(self, resref: str, ext: str) -> str:
        """Return '[Override]' if the resource is overridden, '' otherwise."""
        return '[Override]' if self.has(resref, ext) else ''

    def summary(self) -> str:
        """Human-readable summary of the override index."""
        if not self._scanned:
            return 'OverrideLayer: not yet scanned'
        if not self.is_available:
            return f'OverrideLayer: no Override/ dir at {self._override_dir}'
        by_ext: Dict[str, int] = {}
        for _, entry in self._index.items():
            by_ext[entry.ext] = by_ext.get(entry.ext, 0) + 1
        lines = [f'OverrideLayer: {self.entry_count} files in {self._override_dir}']
        for ext in sorted(by_ext):
            lines.append(f'  .{ext}: {by_ext[ext]} file(s)')
        return '\n'.join(lines)

    # ─────────────────────────────  Model helpers  ──────────────────────────

    def get_model(self, resref: str) -> Optional[bytes]:
        """
        Return MDL bytes for resref from Override/, or None.
        Convenience alias for get(resref, 'mdl').
        """
        return self.get(resref, 'mdl')

    def get_model_mdx(self, resref: str) -> Optional[bytes]:
        """Return MDX companion bytes from Override/, or None."""
        return self.get(resref, 'mdx')

    def get_texture(self, resref: str) -> Optional[bytes]:
        """
        Return texture bytes (TPC preferred, TGA fallback) from Override/.
        Returns None if neither format is present.
        """
        tpc = self.get(resref, 'tpc')
        if tpc is not None:
            return tpc
        return self.get(resref, 'tga')

    def send_to_override(self, resref: str, ext: str, data: bytes) -> Path:
        """
        Write data to Override/<resref>.<ext>, creating Override/ if needed.
        Returns the destination Path.

        This is the 'Send to Override' export button action (Roadmap 12.1).
        After writing, re-indexes the file immediately.
        """
        self._override_dir.mkdir(parents=True, exist_ok=True)
        dest = self._override_dir / f'{resref.lower()}.{ext.lower()}'
        dest.write_bytes(data)
        # Update index immediately
        entry = OverrideEntry(resref=resref.lower(), ext=ext.lower(), path=dest)
        self._index[(entry.resref, entry.ext)] = entry
        log.debug(f'OverrideLayer.send_to_override: wrote {len(data)} B → {dest}')
        return dest

    def delete_override(self, resref: str, ext: str) -> bool:
        """
        Remove Override/<resref>.<ext> from disk and from the index.
        Returns True if the file existed and was deleted.
        """
        key = (resref.lower(), ext.lower())
        entry = self._index.get(key)
        if entry is None:
            return False
        try:
            entry.path.unlink(missing_ok=True)
        except OSError as e:
            log.warning(f'OverrideLayer.delete_override: failed to delete {entry.path}: {e}')
            return False
        del self._index[key]
        return True

    # ─────────────────────────────  Override-aware lookup  ──────────────────

    def get_or_fallback(self, resref: str, ext: str, library) -> Optional[bytes]:
        """
        Override-aware lookup: try Override/ first, fall back to library.

        Parameters
        ----------
        resref : str
        ext    : str     e.g. 'mdl', 'tpc'
        library : object  Any object with a get(resref, ext) → Optional[bytes]
                          method (compatible with GameLibrary and similar).

        Returns bytes or None.
        """
        data = self.get(resref, ext)
        if data is not None:
            return data
        if hasattr(library, 'get'):
            return library.get(resref, ext)
        return None
