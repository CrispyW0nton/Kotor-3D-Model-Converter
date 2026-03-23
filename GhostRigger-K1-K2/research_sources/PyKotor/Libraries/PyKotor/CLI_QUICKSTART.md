# PyKotorCLI Quick Start Guide

## Installation

```bash
# With uv (recommended)
uvx --with-editable Libraries/PyKotor pykotor --help

# Without uv: from repo root, with activated venv
cd PyKotor
python -m pip install -e Libraries/PyKotor
```

## 5-Minute Tutorial

### 1. Create a new project

```bash
PyKotorCLI init mymod
cd mymod
```

This creates:

- `PyKotorCLI.cfg` - Configuration file
- `src/` - Source directory structure
- `.gitignore` - Git ignore file
- `.PyKotorCLI/` - Local config directory

### 2. Unpack an existing module (optional)

```bash
PyKotorCLI unpack --file ~/path/to/mymodule.mod
```

This extracts all files from the module into your `src/` directory, converting GFF files to JSON format.

### 3. View your targets

```bash
PyKotorCLI list
```

Shows all configured targets in your `PyKotorCLI.cfg`.

### 4. Make changes

Edit files in the `src/` directory:

- Scripts: `src/scripts/*.nss`
- Dialogs: `src/dialogs/*.dlg.json`
- Creatures: `src/blueprints/creatures/*.utc.json`
- Areas: `src/areas/*.git.json`, `*.are.json`
- etc.

### 5. Pack your module

```bash
PyKotorCLI pack
```

This will:

1. Convert JSON files to GFF
2. Compile NWScript files
3. Pack everything into a module file

### 6. Install and test

```bash
PyKotorCLI install
```

This installs the packed module to your KOTOR directory.

Or launch the game directly:

```bash
PyKotorCLI play
```

### 7. Diff installs/files with KotorDiff (headless or GUI)

Headless CLI (preferred for automation):

```bash
uvx --refresh pykotor diff --path1 "C:\Games\KOTOR" --path2 "C:\Games\KOTOR_Modded" --filter tat_m17ac --output-mode normal
# Generate incremental TSLPatcher data while diffing
uvx --refresh pykotor diff --path1 "C:\Games\KOTOR" --path2 "C:\Games\KOTOR_Modded" --tslpatchdata .\tslpatchdata --incremental
```

GUI (omit paths or pass `--gui`):

```bash
uvx --refresh kotordiff
```

## Common Workflows

### Starting from scratch

```bash
PyKotorCLI init mynewmod
cd mynewmod
# Create/edit source files
PyKotorCLI pack
```

### Working with an existing module

```bash
PyKotorCLI init mynewmod
cd mynewmod
PyKotorCLI unpack --file ~/modules/existing.mod
# Edit source files
PyKotorCLI install
```

### Testing changes quickly

```bash
PyKotorCLI play
```

This runs convert, compile, pack, install, and launches the game in one command.

### Building multiple targets

```toml
# In PyKotorCLI.cfg
[target]
name = "demo"
file = "demo.mod"

[target]
name = "full"
file = "full.mod"
```

```bash
PyKotorCLI pack all        # Build all targets
PyKotorCLI pack demo       # Build specific target
PyKotorCLI install full    # Install specific target
```

## Configuration

### Global settings

```bash
# Set script compiler path
PyKotorCLI config --global nssCompiler /path/to/nwnnsscomp

# Set KOTOR install directory
PyKotorCLI config --global installDir ~/Documents/KotOR

# List all settings
PyKotorCLI config --list --global
```

### Local (per-project) settings

```bash
PyKotorCLI config --local modName "My Awesome Mod"
PyKotorCLI config --list --local
```

## Tips & Tricks

### Use version control

```bash
cd mymod
git add .
git commit -m "Initial commit"
git remote add origin https://github.com/yourusername/mymod
git push -u origin main
```

### Clean builds

```bash
PyKotorCLI pack --clean
```

Clears the cache before building.

### Skip steps

```bash
PyKotorCLI pack --noConvert    # Don't convert JSON
PyKotorCLI pack --noCompile    # Don't compile scripts
PyKotorCLI install --noPack    # Just install existing file
```

### Compile specific files

```bash
PyKotorCLI compile --file myscript.nss
```

### Verbose output

```bash
PyKotorCLI pack --verbose
PyKotorCLI pack --debug
```

### Quiet mode

```bash
PyKotorCLI pack --quiet
```

## Next Steps

- Read the [README.md](README.md) for full command documentation
- Check [IMPLEMENTATION_NOTES.md](IMPLEMENTATION_NOTES.md) for technical details
- See [PyKotorCLI.cfg examples](https://github.com/squattingmonk/cli#clicfg) (cli-compatible)

## Getting Help

```bash
PyKotorCLI --help
PyKotorCLI <command> --help
```

For issues or questions, visit the [PyKotor repository](https://github.com/OldRepublicDevs/PyKotor).
