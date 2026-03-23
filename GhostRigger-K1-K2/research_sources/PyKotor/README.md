# PyKotor

A Python library for reading and modifying file formats used by the game [Knights of the Old Republic](https://en.wikipedia.org/wiki/Star_Wars:_Knights_of_the_Old_Republic_(video_game)) and its [sequel](https://en.wikipedia.org/wiki/Star_Wars_Knights_of_the_Old_Republic_II:_The_Sith_Lords).

## Table of Contents

- [PyKotor](#pykotor)
  - [Table of Contents](#table-of-contents)
  - [Features](#features)
  - [Requirements](#requirements)
  - [Installation](#installation)
    - [Quick Install](#quick-install)
    - [Standard Install](#standard-install)
  - [Quick Start](#quick-start)
    - [Using the Library](#using-the-library)
    - [Using the Tools](#using-the-tools)
  - [Available Tools](#available-tools)
  - [Documentation](#documentation)
  - [Contributing](#contributing)
  - [License](#license)

## Features

- **Complete file format support** for KotOR and TSL game files
- **Cross-platform** (Windows, macOS, Linux)
- **Holocron Toolset** for modding and development
- **Modern Python** (3.8+)
- **Type-annotated** API with extensive documentation

## Requirements

- Python 3.8+
- Windows 7–11, macOS, or Linux
- All common architectures supported (x86, x64, arm64)

## Installation

### Quick Install

The fastest way to get started is using `uvx` (no installation required). Install `uv` from [Installing uv](https://docs.astral.sh/uv/getting-started/installation/), then run tools with `--refresh` to ensure you're using the latest version:

**Windows (PowerShell):**

```powershell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
uvx --refresh holocrontoolset
```

**macOS/Linux:**

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
uvx --refresh holocrontoolset
```

### Standard Install

**Install the library:**

```bash
pip install pykotor
```

**Install tools:**

```bash
pip install holocrontoolset holopatcher kotordiff
```

**Or use pipx for isolated tool installation:**

```bash
pipx install holocrontoolset
pipx install holopatcher
pipx install kotordiff
```

**Note:** The PyKotor CLI is included with the `pykotor` package and accessible via `pykotor` or `pykotorcli` commands.

See [CONTRIBUTING.md](CONTRIBUTING.md) for development installation. If cloning the repo is slow or stalls, use a shallow clone: `git clone --depth 1 <repo-url>` (see CONTRIBUTING for details).

## Quick Start

### Using the Library

```python
from pykotor.resource.type import ResourceType
from pykotor.extract.installation import Installation
from pykotor.resource.formats.tpc import write_tpc

# Load game installation
inst = Installation("C:/Program Files (x86)/Steam/steamapps/common/swkotor")

# Extract a texture
texture = inst.texture("C_Gammorean01")
write_tpc(texture, "./C_Gammorean01.tga", ResourceType.TGA)
```

### Using the Tools

**HolocronToolset** - GUI editor for KotOR files:

```bash
uvx --refresh holocrontoolset
```

**HoloPatcher** - Cross-platform TSLPatcher alternative:

```bash
uvx --refresh holopatcher --help
```

**PyKotor CLI** - Command-line build tool (included with pykotor):

```bash
uvx --refresh pykotor --help
# Example: convert 2DA to CSV
uvx --refresh pykotor 2da2csv "path/to/file.2da"
```

**KotorDiff** - Compare and generate patches:

```bash
uvx --refresh kotordiff
# or if installed via pip/pipx
kotordiff
```

See individual tool documentation for detailed usage.

## Available Tools

| Tool | Description | Documentation |
|------|-------------|---------------|
| **HolocronToolset** | Full-featured GUI editor for KotOR files | [README](https://github.com/OldRepublicDevs/PyKotor/tree/master/Tools/HolocronToolset#readme) |
| **HoloPatcher** | Fast, cross-platform mod installer | [README](https://github.com/OldRepublicDevs/PyKotor/tree/master/Tools/HoloPatcher#readme) |
| **PyKotor CLI** | Command-line build tool (part of pykotor package) | [Docs](https://github.com/OldRepublicDevs/PyKotor/tree/master/Libraries/PyKotor/docs) |
| **KotorDiff** | File comparison and TSLPatcher data generator | [README](https://github.com/OldRepublicDevs/PyKotor/tree/master/Tools/KotorDiff#readme) |

## Documentation

### User Documentation
- **[Installation & Usage](https://github.com/OldRepublicDevs/PyKotor/tree/master/Libraries/PyKotor/docs)** - Detailed library documentation
- **[Contributing Guide](CONTRIBUTING.md)** - Development setup and guidelines
- **[Project Wiki](https://github.com/OldRepublicDevs/PyKotor/wiki)** - Community documentation
- **[PowerShell Setup](POWERSHELL.md)** - Windows PowerShell configuration

### Design & Architecture
- **[Design System Rules](.cursor/rules/design_system_rules.md)** - Comprehensive UI design system documentation

## Contributing

Contributions are welcome! Please see [CONTRIBUTING.md](CONTRIBUTING.md) for:

- Development environment setup
- Code style guidelines
- Testing procedures
- Pull request process

## License

This project is licensed under the [LGPL-3.0-or-later License](https://github.com/OldRepublicDevs/PyKotor/blob/master/LICENSE).
