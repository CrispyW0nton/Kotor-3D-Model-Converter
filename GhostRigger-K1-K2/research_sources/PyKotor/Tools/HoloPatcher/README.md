# PyKotor TSLPatcher

## Overview

HoloPatcher is a rewrite of TSLPatcher written in Python, utilizing the PyKotor library.

TSLPatcher is a Delphi utility designed for modifying game files for "Star Wars: Knights of the Old Republic" and its sequel. It allows for the seamless integration of mods, ensuring compatibility and minimizing conflicts between different mods.

You can find the [TSLPatcher official readme here.](https://github.com/OldRepublicDevs/PyKotor/wiki/TSLPatcher's-Official-Readme)

However, TSLPatcher is over 20 years old now and many qol features, bugs, and highly popular features were never added over the years.
TSLPatcher, additionally, is closed source, making it difficult to determine its logic or why it may be failing to install a specific mod.


## Goals

- **Backwards Compatibility**: Match TSLPatcher's output and behavior as closely as possible.
- **Cross-platform compatible**: Windows/Mac/Linux will all produce the same patch results. HoloPatcher provides case-insensitive pathing support for all operating systems.
- **Support the non-PC versions of the game**: Support and provide tools for kotor ports such as iOS, android, steamdeck, etc. This goal is largely still in progress.
- **Add new features**: Add highly-requested features while still ensuring backwards compatibility with TSLPatcher.

## Features

- **Configurable Patching**: Offers a flexible system for defining modifications through INI files, allowing for detailed control over file modifications, additions, and compilations.
- **Game File Support**: Supports a wide range of game file types, including GFF, 2DA, TLK, SSF, and NCS/NSS scripts, enabling comprehensive modding capabilities.
- **Memory Management**: Implements a memory system for tracking and reusing modifications across different files, optimizing patching processes and ensuring consistency.
- **Error Handling and Logging**: Provides robust error handling and detailed logging functionality, aiding in debugging and ensuring smooth patching operations.
- **User Interface**: Features a graphical user interface for easy mod installation and management.
- **Command-line support**: Offer a command line for tools such as [KOTORModSync](https://github.com/th3w1zard1/KOTORModSync)
- **Compiling NSS scripts into NCS bytecode without reliance on nwnnsscomp.**

## Usage

_End users should [download the latest release here](https://github.com/OldRepublicDevs/PyKotor/releases)_

HoloPatcher can be used both as a command-line tool and through its graphical user interface.

### Requirements

Install `uv` from [astral-sh/uv installation](https://docs.astral.sh/uv/getting-started/installation/) for the simplest setup.

### Running HoloPatcher

**End users** (latest from PyPI, use `--refresh` for latest):

```bash
uvx --refresh holopatcher
uvx --refresh holopatcher --help
```

**Developers** (local source from PyKotor repo):

```bash
uvx --with-editable Libraries/PyKotor --with-editable Tools/HoloPatcher holopatcher
# or
uv run --directory Tools/HoloPatcher/src --module holopatcher
```

**Without uv** (activated venv): First run `install_python_venv.ps1` at repo root, then:

```bash
python -m pip install -r Tools/HoloPatcher/requirements.txt --prefer-binary
python Tools/HoloPatcher/src/holopatcher/__main__.py <path to game> <path to tslpatchdata> [options]
```

### Command-Line Interface

```bash
# With uv
uvx --refresh holopatcher <path to game> <path to tslpatchdata> [options]

# Without uv (activated venv)
python Tools/HoloPatcher/src/holopatcher/__main__.py <path to game> <path to tslpatchdata> [options]
```
required arguments:

- **--game-dir**: Path to the KOTOR install folder. This will be `mtslrcm` folder or the unpackaged ipa if using one of the mobile games. This is implicit as first argument.
- **--tslpatchdata**: Path to the tslpatchdata folder of the TSLPatcher mod. Can be the parent of tslpatchdata optionally. This is implicit as the second argument.

Options:

- **--install**: Start an immediate install, and do not show a ui window.
- **--console**: Show a console window for extra debug output of HoloPatcher. Using this flag will run HoloPatcher in the current terminal.
- **--uninstall**: Start an uninstall using the most recent backup folder provided in the tslpatchdata argument.
- **--validate**: Validates the specified tslpatchdata mod. More specifically, this runs reader.py to determine if there's any errors in your ini files.


### Graphical User Interface

Simply run the [`src/__main__.py`](https://github.com/OldRepublicDevs/PyKotor/blob/master/Tools/HoloPatcher/src/__main__.py) file without any arguments to launch the GUI.

## Configuration

Modifications are defined in INI files, which specify the files to be patched, the changes to be made, and any additional instructions required for the patching process. The system supports a variety of operations, including:

- Adding or modifying fields in GFF files.
- Inserting or modifying rows in 2DA files.
- Adding or [modifying](https://github.com/OldRepublicDevs/PyKotor/wiki/HoloPatcher-README-for-mod-developers.#tlk-replacements) entries in TLK files.
- Compiling NSS scripts into NCS bytecode without reliance on nwnnsscomp.
- Modifying SSF sound files.

See the TSLPatcher readme for more information.

## Extending

HoloPatcher is designed with extensibility in mind. Developers can extend its functionality by adding new types of modifications or integrating additional game file formats.

## Contributing

Contributions to the PyKotor's HoloPatcher are welcome. Whether it's adding new features, improving existing functionality, or fixing bugs, your contributions are appreciated.

## Further Documentation

For more detailed guides and tutorials on using HoloPatcher, refer to the following resources:

- [Installing Mods with HoloPatcher](https://github.com/OldRepublicDevs/PyKotor/wiki/Installing-Mods-with-HoloPatcher): A step-by-step tutorial on setting up and running HoloPatcher.
- [Advanced Configuration Options](https://github.com/OldRepublicDevs/PyKotor/wiki/HoloPatcher-README-for-mod-developers.): Detailed descriptions of advanced features and how to use them.
- [Mod Creation Best Practices](https://github.com/OldRepublicDevs/PyKotor/wiki/Mod-Creation-Best-Practices): Guidelines and tips for creating mods with HoloPatcher.
- [Notes on Internal Workings](https://github.com/OldRepublicDevs/PyKotor/wiki/Explanations-on-HoloPatcher-Internal-Logic): Explanations on how HoloPatcher works internally and some key TSLPatcher logic.

## License

HoloPatcher is released under the [LGPL-3.0-or-later License](https://github.com/OldRepublicDevs/PyKotor/edit/master/Tools/HoloPatcher/LICENSE.txt).
