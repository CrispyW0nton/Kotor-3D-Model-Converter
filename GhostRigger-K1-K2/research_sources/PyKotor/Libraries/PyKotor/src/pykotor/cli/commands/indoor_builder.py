"""Indoor map building and extraction command implementations for Pykotorcli.

Pykotorcli must not depend on the Holocron Toolset (`toolset.*`). This command layer delegates to
`pykotor.tools.indoormap` / `pykotor.tools.indoorkit` which are library-safe.
"""

from __future__ import annotations

import logging
import sys

from dataclasses import dataclass
from pathlib import Path
from typing import TYPE_CHECKING

from pykotor.cli.indoor_builder import resolve_game_argument
from pykotor.common.indoormap import IndoorMap
from pykotor.common.modulekit import ModuleKitManager
from pykotor.extract.installation import Installation
from pykotor.tools.indoorkit import load_kits
from utility.misc import ensure_directory_exists
from utility.string_util import normalize_string
from pykotor.tools.indoormap import (
    build_mod_from_indoor_file_modulekit,
    extract_indoor_from_module_as_modulekit,
    extract_indoor_from_module_file_against_modulekit,
    extract_indoor_from_module_name,
)
from pykotor.tools.path import CaseAwarePath

if TYPE_CHECKING:
    from argparse import Namespace

    from loggerplus import RobustLogger
    from pykotor.common.indoorkit import Kit
    from pykotor.common.indoormap import MissingRoomInfo
    from pykotor.common.misc import Game

LEVEL_MAP = {
    "debug": logging.DEBUG,
    "info": logging.INFO,
    "warning": logging.WARNING,
    "error": logging.ERROR,
    "critical": logging.CRITICAL,
}


@dataclass(frozen=True)
class _ResolvedContext:
    game: Game
    installation_path: Path
    kits_path: Path | None
    installation: Installation
    kits: list[Kit]


def _apply_log_level(args: Namespace, logger: RobustLogger) -> None:
    """Apply CLI-selected log level when provided."""
    if args.log_level:
        logger.setLevel(LEVEL_MAP.get(args.log_level, logging.INFO))


def _require_cli_value(value: object, *, message: str, logger: RobustLogger) -> bool:
    if value:
        return True
    logger.error("%s", message)
    return False


def _require_cli_values(requirements: list[tuple[object, str]], *, logger: RobustLogger) -> bool:
    """Validate required CLI values and emit first user-facing error."""
    for value, message in requirements:
        if not _require_cli_value(value, message=message, logger=logger):
            return False
    return True


def _report_command_exception(*, logger: RobustLogger, prefix: str, exc: Exception) -> int:
    """Log rich exception details and return consistent non-zero exit code."""
    error_name, msg = (exc.__class__.__name__, str(exc))
    logger.exception("%s: %s: %s", prefix, error_name, msg)
    print(f"[Error] {error_name}: {msg}", file=sys.stderr)  # noqa: T201
    return 1


def _validate_extract_module_args(args: Namespace, module_file_arg: str | None, logger: RobustLogger) -> bool:
    if args.module or module_file_arg:
        return True
    logger.error("No module specified. Use --module <name> or --module-file <path>")
    return False


def _path_exists(path: Path, *, label: str, logger: RobustLogger) -> bool:
    if path.exists():
        return True
    logger.error("%s does not exist: %s", label, path)
    return False


def _paths_exist(paths: list[tuple[Path, str]], *, logger: RobustLogger) -> bool:
    """Validate multiple filesystem paths and short-circuit on first failure."""
    for path, label in paths:
        if not _path_exists(path, label=label, logger=logger):
            return False
    return True


def _log_missing_rooms(logger: RobustLogger, missing: list[MissingRoomInfo]) -> None:
    """Emit compact warning summary for unresolved indoor rooms."""
    if not missing:
        return
    logger.warning("Some rooms could not be loaded: %d missing", len(missing))
    for item in missing[:25]:
        logger.warning("  - Kit '%s', Component '%s': %s", item.kit_name, item.component_name, item.reason)
    if len(missing) > 25:
        logger.warning("  - ... and %d more", len(missing) - 25)


def _write_indoor_output(indoor: IndoorMap, output_path: Path, *, logger: RobustLogger, mode_label: str) -> None:
    """Persist extracted indoor payload and emit standard success logs."""
    output_path.write_bytes(indoor.write())
    logger.info("Extracted indoor map via %s to: %s", mode_label, output_path)
    logger.info("Indoor map extraction completed successfully.")


def _extract_indoor_via_modulekit(
    *,
    module_file_arg: str | None,
    module_name: str,
    candidate_files: list[Path],
    installation_path: Path,
    game: Game,
    logger: RobustLogger,
    installation: Installation,
    module_kit_manager: ModuleKitManager,
) -> IndoorMap | None:
    """Run implicit-kit extraction path for module-name or module-file inputs."""
    if module_file_arg:
        if not module_name:
            logger.error("When using --implicit-kit with --module-file, you must also pass --module <module_root> to specify which ModuleKit to match against.")
            return None
        return extract_indoor_from_module_file_against_modulekit(
            candidate_files[0],
            module_root=module_name,
            installation_path=installation_path,
            game=game,
            logger=logger,
            installation=installation,
            module_kit_manager=module_kit_manager,
        )
    return extract_indoor_from_module_as_modulekit(
        module_name,
        installation_path=installation_path,
        game=game,
        logger=logger,
        installation=installation,
        module_kit_manager=module_kit_manager,
    )


def _module_kit_manager_from_args(args: Namespace, installation: Installation) -> ModuleKitManager:
    """Reuse injected manager in tests or create default manager for runtime."""
    mk_mgr = getattr(args, "_module_kit_manager", None)
    if isinstance(mk_mgr, ModuleKitManager):
        return mk_mgr
    return ModuleKitManager(installation)


def _resolve_module_candidate_files(
    *,
    module_name: str,
    module_file_arg: str | None,
    installation_path: Path,
    logger: RobustLogger,
) -> list[Path] | None:
    if module_file_arg:
        module_file = Path(module_file_arg)
        if not module_file.is_file():
            logger.error("Module file does not exist: %s", module_file)
            return None
        return [module_file]

    modules_dir = installation_path / "modules"
    if not modules_dir.is_dir():
        modules_dir = installation_path / "Modules"

    candidate_files = [
        p
        for ext in (".mod", ".rim", "_s.rim", "_dlg.erf")
        if (p := modules_dir / f"{module_name}{ext}").is_file()
    ]

    if not candidate_files:
        logger.error("No module containers found for '%s' under '%s'", module_name, modules_dir)
        return None

    return candidate_files


def _log_indoor_context(
    logger: RobustLogger,
    *,
    action_label: str,
    installation_path: Path,
    kits_path: Path | None,
    output_path: Path,
    game_name: str,
    implicit_kit: bool,
) -> None:
    logger.info("%s", action_label)
    logger.info("Installation: %s", installation_path)
    if implicit_kit:
        logger.info("Kits: (implicit ModuleKit)")
    else:
        logger.info("Kits: %s", kits_path)
    logger.info("Output: %s", output_path)
    logger.info("Game: %s", game_name)


def _resolve_context(args: Namespace, logger: RobustLogger):
    """Shared setup for indoor-build and indoor-extract.

    Validates installation/kits paths, resolves the game, and returns (game, installation, kits).
    """
    installation_path = Path(args.installation) if args.installation else None
    kits_path = Path(args.kits) if args.kits else None

    if installation_path is None:
        msg = "No installation path specified. Use --installation <path>"
        raise ValueError(msg)
    if not installation_path.exists():
        msg = f"Installation path does not exist: {installation_path}"
        raise ValueError(msg)

    game = resolve_game_argument(args.game, installation_path)
    if game is None:
        msg = "Could not determine game type. Please specify --game k1 or --game k2"
        raise ValueError(msg)

    # Test acceleration hook: allow injecting a pre-warmed Installation object.
    # This is not part of the public CLI surface area; it is only used by tests
    # to avoid re-reading chitin/override/modules repeatedly.
    injected_installation = getattr(args, "_installation_obj", None)
    if isinstance(injected_installation, Installation):
        # Sanity check: do not allow mismatched installation roots.
        try:
            injected_root = Path(injected_installation.path()).resolve()
            cli_root = installation_path.resolve()
        except Exception:
            # If path resolution fails for any reason, fall back to trusting CLI path.
            injected_installation = None
        else:
            if injected_root != cli_root:
                msg = f"Injected Installation root does not match --installation: {injected_installation.path()} != {installation_path}"
                raise ValueError(msg)

    installation = injected_installation or Installation(CaseAwarePath(installation_path))
    if args.implicit_kit:
        logger.debug("Implicit-kit mode enabled (ModuleKit). External kits will not be loaded.")
        return _ResolvedContext(game=game, installation_path=installation_path, kits_path=kits_path, installation=installation, kits=[])

    if kits_path is None:
        msg = "No kits directory specified. Use --kits <path> (or pass --implicit-kit)"
        raise ValueError(msg)
    if not kits_path.exists():
        msg = f"Kits directory does not exist: {kits_path}"
        raise ValueError(msg)

    kits = load_kits(kits_path)
    logger.debug("Loaded %d kit(s) from '%s'", len(kits), kits_path)
    return _ResolvedContext(game=game, installation_path=installation_path, kits_path=kits_path, installation=installation, kits=kits)


def cmd_indoor_build(args: Namespace, logger: RobustLogger) -> int:  # noqa: PLR0911, PLR0912, PLR0915
    """Build a .mod file from a .indoor file.

    This command loads a .indoor JSON file and builds it into a complete .mod file
    using the specified kits and installation resources.

    Args:
    ----
        args: Parsed command-line arguments
        logger: Logger instance

    Returns:
    -------
        Exit code (0 for success, non-zero for failure)
    """
    _apply_log_level(args, logger)

    # Validate inputs
    if not _require_cli_values(
        [
            (args.input, "No input .indoor file specified. Use --input <path>"),
            (args.output, "No output .mod file specified. Use --output <path>"),
            (args.installation, "No installation path specified. Use --installation <path>"),
        ],
        logger=logger,
    ):
        return 1
    if not args.implicit_kit and not args.kits:
        logger.error("No kits directory specified. Use --kits <path> (or pass --implicit-kit)")
        return 1

    input_path = Path(args.input)
    output_path = Path(args.output)
    installation_path = Path(args.installation)
    kits_path = Path(args.kits) if args.kits else None

    # Validate paths exist
    required_paths: list[tuple[Path, str]] = [
        (input_path, "Input file"),
        (installation_path, "Installation path"),
    ]
    if not args.implicit_kit:
        assert kits_path is not None
        required_paths.append((kits_path, "Kits directory"))
    if not _paths_exist(
        required_paths,
        logger=logger,
    ):
        return 1

    try:
        context = _resolve_context(args, logger)
        game = context.game
        installation = context.installation
        kits = context.kits

        _log_indoor_context(
            logger,
            action_label=f"Building module from indoor map: {input_path.name}",
            installation_path=installation_path,
            kits_path=kits_path,
            output_path=output_path,
            game_name=game.name,
            implicit_kit=args.implicit_kit,
        )

        if args.implicit_kit:
            mk_mgr = _module_kit_manager_from_args(args, installation)
            build_mod_from_indoor_file_modulekit(
                input_path,
                output_mod_path=output_path,
                installation_path=installation_path,
                game=game,
                module_id=args.module_filename,
                loadscreen_path=args.loading_screen,
                installation=installation,
                module_kit_manager=mk_mgr,
            )
        else:
            indoor = IndoorMap()
            missing = indoor.load(input_path.read_bytes(), kits)
            _log_missing_rooms(logger, missing)

            if args.module_filename:
                indoor.module_id = normalize_string(args.module_filename)
                logger.info("Module ID set to: %s", indoor.module_id)

            indoor.build(installation, kits, output_path, game_override=game, loadscreen_path=args.loading_screen)

    except Exception as exc:
        return _report_command_exception(logger=logger, prefix="Indoor map build failed", exc=exc)
    else:
        logger.info("Indoor map build completed successfully.")
        return 0


def cmd_indoor_extract(args: Namespace, logger: RobustLogger) -> int:  # noqa: PLR0911, PLR0912, PLR0915
    """Extract a .indoor file from a composite module.

    This command extracts module data from composite files (_s.rim/.rim/_dlg.erf)
    and converts it to a .indoor JSON file. This is a complex reverse-engineering
    process that attempts to match module rooms back to their source kits.

    Args:
    ----
        args: Parsed command-line arguments
        logger: Logger instance

    Returns:
    -------
        Exit code (0 for success, non-zero for failure)
    """
    _apply_log_level(args, logger)

    # Validate inputs
    module_file_arg = getattr(args, "module_file", None)
    if not _validate_extract_module_args(args, module_file_arg, logger):
        return 1
    if not _require_cli_values(
        [
            (args.output, "No output .indoor file specified. Use --output <path>"),
            (args.installation, "No installation path specified. Use --installation <path>"),
        ],
        logger=logger,
    ):
        return 1
    # kits are optional in implicit-kit mode.

    module_name = normalize_string(args.module) if args.module else ""
    output_path = Path(args.output)
    installation_path = Path(args.installation)
    kits_path = Path(args.kits) if args.kits else None

    try:
        context = _resolve_context(args, logger)
        game = context.game
        installation = context.installation

        action_label = (
            f"Extracting indoor map from module file: {module_file_arg}"
            if module_file_arg
            else f"Extracting indoor map from module: {module_name}"
        )
        _log_indoor_context(
            logger,
            action_label=action_label,
            installation_path=installation_path,
            kits_path=kits_path,
            output_path=output_path,
            game_name=game.name,
            implicit_kit=args.implicit_kit,
        )

        module_candidates = _resolve_module_candidate_files(
            module_name=module_name,
            module_file_arg=module_file_arg,
            installation_path=installation_path,
            logger=logger,
        )
        if module_candidates is None:
            return 1
        candidate_files = module_candidates

        ensure_directory_exists(output_path.parent)

        # NOTE: We do not use embedded `indoormap.txt` payloads. Extraction must be based on
        # real module resources (LYT/WOK/MDL/MDX/etc), not cached editor data.

        if args.implicit_kit:
            mk_mgr = _module_kit_manager_from_args(args, installation)
            indoor = _extract_indoor_via_modulekit(
                module_file_arg=module_file_arg,
                module_name=module_name,
                candidate_files=candidate_files,
                installation_path=installation_path,
                game=game,
                logger=logger,
                installation=installation,
                module_kit_manager=mk_mgr,
            )
            if indoor is None:
                return 1
            _write_indoor_output(indoor, output_path, logger=logger, mode_label="ModuleKit")
            return 0

        if kits_path is None:
            logger.error("No kits directory specified. Use --kits <path> (or pass --implicit-kit)")
            return 1

        # Full reverse-extraction path: rebuild `.indoor` by matching room WOKs back to kits.
        logger.info("Attempting full reverse-extraction from module resources...")
        indoor = extract_indoor_from_module_name(
            module_name,
            installation_path=installation_path,
            kits_path=kits_path,
            game=game,
            strict=True,
            logger=logger,
        )
        _write_indoor_output(indoor, output_path, logger=logger, mode_label="reverse-extraction")
    except Exception as exc:
        return _report_command_exception(logger=logger, prefix="Indoor map extraction failed", exc=exc)
    return 0
