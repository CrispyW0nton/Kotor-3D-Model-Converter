# PyKotor

[![PyPI](https://img.shields.io/pypi/v/pykotor.svg)](https://pypi.org/project/pykotor/)
[![docs](https://img.shields.io/badge/docs-wiki-blue.svg)](https://github.com/OldRepublicDevs/PyKotor/wiki)
[![license: LGPL v3+](https://img.shields.io/badge/license-LGPL%20v3%2B-lightgrey.svg)](https://www.gnu.org/licenses/lgpl-3.0.html)
[![CI](https://github.com/OldRepublicDevs/PyKotor/actions/workflows/ci.yml/badge.svg)](https://github.com/OldRepublicDevs/PyKotor/actions/workflows/ci.yml)
[![pre-commit](https://results.pre-commit.ci/badge/github/OldRepublicDevs/PyKotor/main.svg)](https://results.pre-commit.ci/latest/github/OldRepublicDevs/PyKotor/main)

**PyKotor** is a modern Python library and toolset for reading, writing, and modding resources from the Star Wars: Knights of the Old Republic (KOTOR, K1) and The Sith Lords (KOTOR II, TSL) game engines.

---

## Features

- Read and write almost all K1/TSL resource and file formats (BIF, ERF, GFF, KEY, TLK, DLG, UTC, UTP, UTI, UTS, etc.)
- Support for both K1 (*swkotor.exe*) and TSL (*swkotor2.exe*) with unified APIs
- High-fidelity, reverse-engineered format logic and type safety
- Command-line toolkit (`pykotorcli`) for file conversion, inspection, and batch operations
- Programmatic API for advanced automation and mod tooling
- Modern, type-checked, actively maintained, and well-tested codebase

## Documentation & Community

- 📚 **Docs / Usage:** [Wiki & Getting Started](https://github.com/OldRepublicDevs/PyKotor/wiki)
- 🐛 **Bugs:** [GitHub Issues](https://github.com/OldRepublicDevs/PyKotor/issues)
- 💬 **Community Discord:** [Invite Link](https://discord.gg/4bEyeF3)
- 🌟 **Changelog:** [Releases](https://github.com/OldRepublicDevs/PyKotor/releases)

## Quick Install

```bash
pip install pykotor
```

Or with extras for format encodings and update tool:
```bash
pip install "pykotor[encodings,updater]"
```

## CLI Example

```bash
# Convert a BIF file to readable resources
pykotorcli extract-bif --input KOTOR1/BIFs/data.bif --output ./output_dir

# Inspect a GFF (generic file format)
pykotorcli gff-dump --file some_file.uti

# See all CLI features
pykotorcli --help
```

## Python Usage Example

```python
from pykotor.tsl.gff import GFF

# Parse a .utc (creature) file
gff = GFF.parse("dan13_01.utc")
print(gff.root["FirstName"].string)  # Accessing the field value

# Modify and save
gff.root["FirstName"].string = "HK-47"
gff.write("hk_utc.gff")
```

## Supported Formats

Major types:
- Containers: BIF, ERF, KEY, MOD, RIM
- Resources: GFF/UT*, GIT, DLG, ARE, UTP, UTI, UTC, UTS, UTM, UTR, UTT, JRL, TLK, etc.
- 2DA, SSF, NCS/NSS, NDB, models, textures, etc.
See [Wiki Format Coverage](https://github.com/OldRepublicDevs/PyKotor/wiki/Format-Support-Matrix).

## Development & Contributing

1. Clone the repo and install [Poetry](https://python-poetry.org/) or use `uv`.
2. `poetry install` or `uv pip install -e .[dev]`
3. Run `pytest` and `ruff check .` and `mypy --strict` before submitting PRs.

For feature requests, new formats, or reverse-engineering findings, see [CONTRIBUTING.md](https://github.com/OldRepublicDevs/PyKotor/blob/master/CONTRIBUTING.md).

---

## License

LGPL-3.0-or-later (see [LICENSE](https://github.com/OldRepublicDevs/PyKotor/blob/master/LICENSE))

---

> This project follows unified K1/TSL reverse engineering practices. All resource logic is verified across both game engines using REVA MCP tools. See the [Wiki](https://github.com/OldRepublicDevs/PyKotor/wiki/Reverse-Engineering-Workflow) for details on our protocol.


