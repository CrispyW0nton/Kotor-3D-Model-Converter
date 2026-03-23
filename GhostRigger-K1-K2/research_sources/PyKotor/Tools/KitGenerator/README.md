# Kit Generator

Kit Generator GUI for PyKotor CLI - generates Holocron-compatible kits from KOTOR module files (RIM/ERF).

This is a shim package that provides a standalone GUI entry point. The core functionality is in `pykotor.cli.commands.kit_generate`.

## Installation

**End users** (use `--refresh` for latest):

```bash
uvx --refresh pykotor kit-generate --help
uvx --refresh pykotor kit-generate --gui
```

**Developers** (local source):

```bash
uvx --with-editable Libraries/PyKotor pykotor kit-generate --installation <path> --module <module> --output <dir>
uv run --directory Libraries/PyKotor/src --module pykotor kit-generate --installation <path> --module <module> --output <dir>
```

**Without uv** (activated venv): `pip install kit-generator` or `pip install -e Tools/KitGenerator`

## Usage

### GUI Mode

```bash
uvx --refresh pykotor kit-generate --gui
# or: python -m kitgenerator when installed via pip
```

### CLI Mode

```bash
uvx --refresh pykotor kit-generate --installation <path> --module <module> --output <dir>
```

## Features

- Extract kit resources from KOTOR module files (RIM/ERF)
- Generate Holocron-compatible kit structures
- Interactive GUI for selecting installation, module, and output directory
- Headless CLI mode for automation

## License

LGPL-3.0-or-later
