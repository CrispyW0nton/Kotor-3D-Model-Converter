"""Case-aware path helpers used by PyKotor.

The module keeps modern `pathlib` behavior where possible, while preserving
legacy compatibility points that older callers still import from here.
"""
from __future__ import annotations

import os
import pathlib
import re
import sys
import warnings

from functools import lru_cache
from typing import TYPE_CHECKING

from loggerplus import RobustLogger  # pyright: ignore[reportMissingTypeStubs, reportMissingModuleSource]

if TYPE_CHECKING:
    from collections.abc import Iterable

    from pykotor.common.misc import Game

# Directory cache
# Key: directory path string, Value: (mtime, dict mapping lowercase->list)
_DIR_CACHE: dict[str, tuple[int, dict[str, list[str]]]] = {}
_DIR_CACHE_MAX_SIZE = 4096
_WINDOWS_PATH_NORMALIZE_RE = re.compile(r"^\\{3,}")
_WINDOWS_EXTRA_SLASHES_RE = re.compile(r"(?<!^)\\+")
_UNIX_EXTRA_SLASHES_RE = re.compile(r"/{2,}")


def _warn_deprecated_endpoint(endpoint: str, replacement: str) -> None:
    """Emit a deprecation warning for legacy path.py compatibility endpoints."""
    RobustLogger().debug("Deprecated path API used: %s", endpoint)
    warnings.warn(
        f"`{endpoint}` is deprecated and will be removed in a future release. {replacement}",
        DeprecationWarning,
        stacklevel=3,
    )


def is_filesystem_case_sensitive(
    path: os.PathLike | str,
) -> bool | None:
    """Check if the filesystem at the given path is case-sensitive.
    This function creates a temporary file to test the filesystem behavior.
    """
    import tempfile

    try:
        with tempfile.TemporaryDirectory(dir=path) as temp_dir:
            temp_path: pathlib.Path = pathlib.Path(temp_dir)
            test_file: pathlib.Path = temp_path / "case_test_file"
            test_file.touch()

            # Attempt to access the same file with a different case to check case sensitivity
            test_file_upper: pathlib.Path = temp_path / "CASE_TEST_FILE"
            return not test_file_upper.exists()
    except Exception:  # noqa: BLE001
        RobustLogger().debug("Failed to detect filesystem case sensitivity for '%s'.", path, exc_info=True)
        return None


def _get_dir_contents(path_str: str) -> dict[str, list[str]]:
    """Build a case-insensitive directory lookup table for one directory.

    The returned mapping is:
        lowercase entry name -> list of actual names in that directory
    """
    try:
        stat = os.stat(path_str)
        mtime_ns = getattr(stat, "st_mtime_ns", int(stat.st_mtime * 1_000_000_000))
    except OSError:
        # Directory doesn't exist or is not accessible
        RobustLogger().debug("Cannot stat directory while building case map: '%s'.", path_str, exc_info=True)
        return {}

    # Directory-level cache keyed by mtime_ns.
    # This gives a large speedup in repeated path resolution while still staying safe.
    cached = _DIR_CACHE.get(path_str)
    if cached is not None and cached[0] == mtime_ns:
        return cached[1]

    mapping: dict[str, list[str]] = {}
    try:
        with os.scandir(path_str) as entries:
            for entry in entries:
                lower = entry.name.lower()
                if lower not in mapping:
                    mapping[lower] = []
                mapping[lower].append(entry.name)
    except OSError:
        RobustLogger().debug("Cannot scan directory while building case map: '%s'.", path_str, exc_info=True)

    # Keep cache bounded.
    if path_str not in _DIR_CACHE and len(_DIR_CACHE) >= _DIR_CACHE_MAX_SIZE:
        _DIR_CACHE.pop(next(iter(_DIR_CACHE)))
    _DIR_CACHE[path_str] = (mtime_ns, mapping)
    return mapping


def _choose_case_match(part: str, matches: list[str], current_path: str) -> str:
    """Choose the best match for an ambiguously-cased path segment."""
    if len(matches) == 1:
        return matches[0]
    if part in matches:
        return part

    best_match = matches[0]
    best_score = -1
    for candidate in matches:
        score = CaseAwarePath.get_matching_characters_count(part, candidate)
        if score > best_score:
            best_score = score
            best_match = candidate

    RobustLogger().debug(
        "Ambiguous case-insensitive match for '%s' under '%s'; chose '%s' from %s.",
        part,
        current_path,
        best_match,
        matches,
    )
    return best_match


def clear_cache() -> None:
    """Clear directory case-resolution cache."""
    cached_entries = len(_DIR_CACHE)
    _DIR_CACHE.clear()
    if cached_entries:
        RobustLogger().info("Cleared CaseAwarePath directory cache (%s entries).", cached_entries)


class CaseAwarePath(pathlib.Path):
    """Pathlib path with case-insensitive resolution for POSIX filesystems.

    This class intentionally preserves old behavior for mixed slash handling and
    legacy utility-style helpers while still relying on pathlib for core path ops.
    """

    # pathlib subclassing mechanism (pre-3.14)
    if hasattr(pathlib, "_windows_flavour"):
        _flavour = pathlib._windows_flavour if os.name == "nt" else pathlib._posix_flavour

    @staticmethod
    def _normalize_posix_constructor_arg(arg: object) -> object:
        """Normalize a constructor argument for POSIX path semantics."""
        if isinstance(arg, (os.PathLike, pathlib.PurePath)):
            arg = os.fspath(arg)
        if isinstance(arg, bytes):
            arg = os.fsdecode(arg)
        if isinstance(arg, str):
            return arg.replace("\\", "/")
        return arg

    @classmethod
    def _normalize_posix_constructor_args(cls, args: tuple[object, ...]) -> tuple[object, ...]:
        """Normalize constructor arguments for POSIX path semantics."""
        return tuple(cls._normalize_posix_constructor_arg(arg) for arg in args)

    @classmethod
    def _normalize_posix_raw_paths(cls, args: tuple[object, ...]) -> list[str]:
        """Return string raw-path arguments normalized for pathlib internals on POSIX."""
        normalized_raw_paths: list[str] = []
        for arg in cls._normalize_posix_constructor_args(args):
            if isinstance(arg, str):
                normalized_raw_paths.append(arg)
                continue
            arg_path = os.fspath(arg)
            if isinstance(arg_path, bytes):
                arg_path = os.fsdecode(arg_path)
            normalized_raw_paths.append(arg_path.replace("\\", "/"))
        return normalized_raw_paths

    def __new__(cls, *args, **kwargs):
        if os.name == "posix":
            args = cls._normalize_posix_constructor_args(args)
        return super().__new__(cls, *args, **kwargs)

    def __init__(self, *args, **kwargs):
        """Normalize raw constructor paths for Python 3.12+ pathlib internals.

        Python 3.12+ stores original constructor arguments in `_raw_paths` during
        `__init__`, so `__new__`-only normalization is insufficient.
        """
        # Python < 3.12 can route to object.__init__, which does not accept args.
        if sys.version_info >= (3, 12):
            super().__init__(*args, **kwargs)
        else:
            super().__init__()
        # `_raw_paths` is a CPython pathlib implementation detail used in 3.12+.
        # We only touch it when present.
        if os.name != "posix" or not hasattr(self, "_raw_paths"):
            return

        self._raw_paths = self._normalize_posix_raw_paths(args)  # type: ignore[attr-defined]

    @staticmethod
    def _is_windows_drive_like(path: str) -> bool:
        return len(path) >= 2 and path[1] == ":" and path[0].isalpha()

    def _resolve_path(self) -> str:
        """Return a normalized path string with best-effort case correction.

        On POSIX, this performs segment-by-segment resolution using case-insensitive
        directory scans whenever an exact segment does not exist.
        """
        if os.name == "nt":
            return super().__str__()

        raw_path = self.str_norm(super().__str__(), slash="/")

        # Preserve Windows-drive-like paths when running on POSIX
        # (e.g. "C:/Users/test"), which are relative segments here.
        if self._is_windows_drive_like(raw_path):
            return raw_path

        # Fast path for correctly-cased existing paths.
        if os.path.exists(raw_path):
            return raw_path

        parts = pathlib.PurePosixPath(raw_path).parts
        if not parts:
            return "."

        is_absolute = self.is_absolute()
        if is_absolute:
            current_path = parts[0]
            start_index = 1
        else:
            current_path = os.getcwd()
            start_index = 0

        # Resolve each segment case-insensitively until we can no longer match.
        for i in range(start_index, len(parts)):
            part = parts[i]
            if part in {".", ".."}:
                current_path = os.path.join(current_path, part)
                continue

            exact_child = os.path.join(current_path, part)
            if os.path.exists(exact_child):
                current_path = exact_child
                continue

            contents = _get_dir_contents(current_path)
            matches = contents.get(part.lower())
            if matches:
                actual_name = _choose_case_match(part, matches, current_path)
                current_path = os.path.join(current_path, actual_name)
            else:
                remaining = parts[i:]
                RobustLogger().debug(
                    "No case-insensitive match for segment '%s' under '%s'; preserving remaining segments %s.",
                    part,
                    current_path,
                    remaining,
                )
                current_path = os.path.join(current_path, *remaining)
                break

        if not is_absolute:
            cwd = os.getcwd()
            if current_path == cwd:
                relative_path = "."
            elif current_path.startswith(f"{cwd}{os.sep}"):
                relative_path = current_path[len(cwd) + 1 :]
            else:
                relative_path = current_path
            return self.str_norm(relative_path, slash=os.sep)

        return self.str_norm(current_path, slash=os.sep)

    def __fspath__(self) -> str:
        return self._resolve_path()

    def __hash__(self) -> int:
        return hash(str(self).lower())

    def __eq__(self, other):
        if not isinstance(other, (str, os.PathLike)):
            return NotImplemented
        s1 = str(self).lower()
        s2 = str(other).lower()
        if os.sep == "/":
            s1 = s1.replace("\\", "/")
            s2 = s2.replace("\\", "/")
        else:
            s1 = s1.replace("/", "\\")
            s2 = s2.replace("/", "\\")

        return s1 == s2

    def __str__(self) -> str:
        return self._resolve_path()

    @property
    def name(self) -> str:
        # Use PurePosixPath for mixed slash compatibility on POSIX.
        return pathlib.PurePosixPath(str(self).replace("\\", "/")).name

    def endswith(self, suffix: str) -> bool:
        return str(self).lower().endswith(suffix.lower())

    def is_relative_to(self, other: str | os.PathLike, *other_parts: str | os.PathLike) -> bool:
        if other_parts:
            _warn_deprecated_endpoint(
                "CaseAwarePath.is_relative_to(path, *segments)",
                "Pass a single path object (or pre-join the segments).",
            )
            other = CaseAwarePath(other, *other_parts)
        try:
            self.relative_to(other)
            return True
        except ValueError:
            return False

    def relative_to(self, other: str | os.PathLike, *other_parts: str | os.PathLike) -> CaseAwarePath:
        if other_parts:
            _warn_deprecated_endpoint(
                "CaseAwarePath.relative_to(path, *segments)",
                "Pass a single path object (or pre-join the segments).",
            )
            other = CaseAwarePath(other, *other_parts)

        my_path = os.path.abspath(str(self._resolve_path()))
        if isinstance(other, CaseAwarePath):
            other_path = str(other)
        else:
            other_path = str(CaseAwarePath(other))
        other_path = os.path.abspath(other_path)

        if os.sep == "\\":
            my_path = my_path.replace("/", "\\")
            other_path = other_path.replace("/", "\\")

        if my_path.lower().startswith(other_path.lower()):
            rel_str = my_path[len(other_path) :]
            rel_str = rel_str.lstrip(os.sep)
            if not rel_str:
                return CaseAwarePath(".")
            return CaseAwarePath(rel_str)
        raise ValueError(f"{self} is not relative to {other}")

    @staticmethod
    def str_norm(path: str, slash: str = "/") -> str:
        """Normalizes a path string while preserving `..` parts."""
        if slash not in {"\\", "/"}:
            raise ValueError(f"Invalid slash str: '{slash}'")

        normalized = path.strip('"').strip()
        if not normalized:
            return "."

        if slash == "\\":
            normalized = normalized.replace("/", "\\").replace("\\.\\", "\\")
            normalized = _WINDOWS_PATH_NORMALIZE_RE.sub(r"\\", normalized)
            normalized = _WINDOWS_EXTRA_SLASHES_RE.sub(r"\\", normalized)
        else:
            normalized = normalized.replace("\\", "/").replace("/./", "/")
            normalized = _UNIX_EXTRA_SLASHES_RE.sub("/", normalized)

        if len(normalized) != 1:
            normalized = normalized.rstrip(slash)
        return normalized or "."

    @classmethod
    def find_closest_match(cls, target: str, candidates: Iterable[os.PathLike | str]) -> str:
        target_lower = target.lower()
        candidates_list = list(candidates)

        best_match = target
        best_score = -1
        found = False

        for cand in candidates_list:
            cand_name = cand.name if isinstance(cand, os.PathLike) else str(cand)
            if cand_name.lower() == target_lower:
                found = True
                score = cls.get_matching_characters_count(target, cand_name)
                if score > best_score:
                    best_score = score
                    best_match = cand_name
        return best_match if found else target

    @staticmethod
    @lru_cache(maxsize=10000)
    def get_matching_characters_count(str1: str, str2: str) -> int:
        return sum(a == b for a, b in zip(str1, str2)) if str1.lower() == str2.lower() else -1

    @staticmethod
    def extract_absolute_prefix(relative_path: os.PathLike | str, absolute_path: os.PathLike | str) -> tuple[str, ...]:
        _warn_deprecated_endpoint(
            "CaseAwarePath.extract_absolute_prefix()",
            "Use pathlib path decomposition instead.",
        )
        absolute = pathlib.Path(absolute_path).absolute()
        relative_resolved = (absolute.parent / relative_path).absolute()
        abs_parts = absolute.parts
        rel_parts = relative_resolved.parts
        start_index_of_rel_in_abs = len(abs_parts) - len(rel_parts)
        return abs_parts[:start_index_of_rel_in_abs]

    @classmethod
    def get_case_sensitive_path(
        cls,
        path: str | os.PathLike,
        prefixes: list[str] | tuple[str, ...] | None = None,
    ) -> CaseAwarePath:
        if prefixes is not None:
            _warn_deprecated_endpoint(
                "CaseAwarePath.get_case_sensitive_path(path, prefixes=...)",
                "Construct a CaseAwarePath from full path segments instead.",
            )
        if prefixes:
            return cls(*prefixes, path)
        return cls(path)


def _get_case_insensitive_path_fast(
    path: str,
    ret_found: bool = False,  # noqa: FBT001, FBT002
) -> tuple[str, bool] | str:
    """Deprecated compatibility shim for old callers."""
    _warn_deprecated_endpoint(
        "_get_case_insensitive_path_fast()",
        "Use CaseAwarePath.get_case_sensitive_path().",
    )
    resolved = str(CaseAwarePath.get_case_sensitive_path(path))
    if ret_found:
        return resolved, os.path.exists(resolved)
    return resolved


def simple_wrapper(fn_name: str, wrapped_class_type: type[CaseAwarePath]):
    """Deprecated compatibility shim for old caller imports."""
    _warn_deprecated_endpoint(
        "simple_wrapper()",
        "This compatibility wrapper is no longer required.",
    )

    def wrapped(self: CaseAwarePath, *args, **kwargs):
        method = getattr(wrapped_class_type, fn_name)
        return method(self, *args, **kwargs)

    return wrapped


def create_case_insensitive_pathlib_class(cls: type[CaseAwarePath]) -> None:
    """Deprecated no-op retained for import compatibility."""
    _warn_deprecated_endpoint(
        "create_case_insensitive_pathlib_class()",
        "CaseAwarePath now manages compatibility behavior internally.",
    )
    return None


def _deprecated_noop(endpoint: str, replacement: str) -> None:
    _warn_deprecated_endpoint(endpoint, replacement)
    return None


def _cleanup_fuse_mounts() -> None:
    """Deprecated no-op: FUSE mount support was removed from this module."""
    _deprecated_noop(
        "_cleanup_fuse_mounts()",
        "FUSE path mounting support was removed from this module.",
    )


def _get_or_create_fuse_mount(root_path: str) -> str | None:
    """Deprecated no-op: FUSE mount support was removed from this module."""
    _deprecated_noop(
        "_get_or_create_fuse_mount()",
        "FUSE path mounting support was removed from this module.",
    )
    return None


def get_default_paths() -> dict[str, dict[Game, list[str]]]:  # TODO(th3w1zard1): Many of these paths are incomplete and need community input.  # noqa: TD003
    from pykotor.common.misc import Game  # noqa: PLC0415  # pylint: disable=import-outside-toplevel

    return {
        "Windows": {
            Game.K1: [
                r"C:\Program Files\Steam\steamapps\common\swkotor",
                r"C:\Program Files (x86)\Steam\steamapps\common\swkotor",
                r"C:\Program Files\LucasArts\SWKotOR",
                r"C:\Program Files (x86)\LucasArts\SWKotOR",
                r"C:\GOG Games\Star Wars - KotOR",
                r"C:\Amazon Games\Library\Star Wars - Knights of the Old",
            ],
            Game.K2: [
                r"C:\Program Files\Steam\steamapps\common\Knights of the Old Republic II",
                r"C:\Program Files (x86)\Steam\steamapps\common\Knights of the Old Republic II",
                r"C:\Program Files\LucasArts\SWKotOR2",
                r"C:\Program Files (x86)\LucasArts\SWKotOR2",
                r"C:\GOG Games\Star Wars - KotOR2",
            ],
        },
        "Darwin": {
            Game.K1: [
                "~/Library/Application Support/Steam/steamapps/common/swkotor/Knights of the Old Republic.app/Contents/Assets",  # Verified
                "~/Library/Applications/Steam/steamapps/common/swkotor/Knights of the Old Republic.app/Contents/Assets/",
            ],
            Game.K2: [
                "~/Library/Application Support/Steam/steamapps/common/Knights of the Old Republic II/Knights of the Old Republic II.app/Contents/Assets",
                "~/Library/Applications/Steam/steamapps/common/Knights of the Old Republic II/Star Wars™: Knights of the Old Republic II.app/Contents/GameData",
                "~/Library/Application Support/Steam/steamapps/common/Knights of the Old Republic II/KOTOR2.app/Contents/GameData/",  # Verified
                "~/Applications/Knights of the Old Republic 2.app/Contents/Resources/transgaming/c_drive/Program Files/SWKotOR2/",
                "/Applications/Knights of the Old Republic 2.app/Contents/Resources/transgaming/c_drive/Program Files/SWKotOR2/",
            ],
        },
        "Linux": {
            Game.K1: [
                # Steam
                "~/.local/share/steam/common/steamapps/swkotor",
                "~/.steam/root/steamapps/common/swkotor",
                "~/.steam/debian-installation/steamapps/common/swkotor",
                # Flatpak Steam
                "~/.var/app/com.valvesoftware.Steam/.local/share/Steam/steamapps/common/swkotor",
                # WSL Defaults
                "/mnt/C/Program Files/Steam/steamapps/common/swkotor",
                "/mnt/C/Program Files (x86)/Steam/steamapps/common/swkotor",
                "/mnt/C/Program Files/LucasArts/SWKotOR",
                "/mnt/C/Program Files (x86)/LucasArts/SWKotOR",
                "/mnt/C/GOG Games/Star Wars - KotOR",
                "/mnt/C/Amazon Games/Library/Star Wars - Knights of the Old",
            ],
            Game.K2: [
                # Steam
                "~/.local/share/Steam/common/steamapps/Knights of the Old Republic II",
                "~/.steam/root/steamapps/common/Knights of the Old Republic II",
                "~/.steam/debian-installation/steamapps/common/Knights of the Old Republic II",
                # Aspyr Port Saves
                "~/.local/share/aspyr-media/kotor2",
                # Flatpak Steam
                "~/.var/app/com.valvesoftware.Steam/.local/share/Steam/steamapps/common/Knights of the Old Republic II/steamassets",
                # WSL Defaults
                "/mnt/C/Program Files/Steam/steamapps/common/Knights of the Old Republic II",
                "/mnt/C/Program Files (x86)/Steam/steamapps/common/Knights of the Old Republic II",
                "/mnt/C/Program Files/LucasArts/SWKotOR2",
                "/mnt/C/Program Files (x86)/LucasArts/SWKotOR2",
                "/mnt/C/GOG Games/Star Wars - KotOR2",
            ],
        },
    }


def find_kotor_paths_from_default() -> dict[Game, list[CaseAwarePath]]:
    """Finds paths to Knights of the Old Republic game data directories.

    Returns:
    -------
        dict[Game, list[CaseAwarePath]]: A dictionary mapping Games to lists of existing path locations.
    """
    import platform

    from pykotor.common.misc import Game  # noqa: PLC0415

    os_str = platform.system()

    # Build hardcoded default kotor locations
    raw_locations: dict[str, dict[Game, list[str]]] = get_default_paths()
    locations: dict[Game, set[CaseAwarePath]] = {
        game: {case_path for case_path in (CaseAwarePath(path).expanduser().resolve() for path in paths) if case_path.exists()}
        for game, paths in raw_locations.get(os_str, {}).items()
    }

    # Build kotor locations by registry (if on windows)
    if os_str == "Windows":
        from pykotor.tools.registry import find_software_key, resolve_reg_key_to_path, winreg_key

        for game, possible_game_paths in ((Game.K1, winreg_key(Game.K1)), (Game.K2, winreg_key(Game.K2))):
            for reg_key, reg_valname in possible_game_paths:
                path_str = resolve_reg_key_to_path(reg_key, reg_valname)
                path = CaseAwarePath(path_str).resolve() if path_str else None
                if path and path.name and path.is_dir():
                    locations[game].add(path)

        amazon_k1_path_str: str | None = find_software_key("AmazonGames/Star Wars - Knights of the Old")
        if amazon_k1_path_str is not None and os.path.isdir(amazon_k1_path_str):
            locations[Game.K1].add(CaseAwarePath(amazon_k1_path_str))

    return {Game.K1: sorted(list(locations[Game.K1])), Game.K2: sorted(list(locations[Game.K2]))}


__all__ = [
    "CaseAwarePath",
    "_cleanup_fuse_mounts",
    "_get_case_insensitive_path_fast",
    "_get_or_create_fuse_mount",
    "clear_cache",
    "create_case_insensitive_pathlib_class",
    "find_kotor_paths_from_default",
    "get_default_paths",
    "is_filesystem_case_sensitive",
    "simple_wrapper",
]
