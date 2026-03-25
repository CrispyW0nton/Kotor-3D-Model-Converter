# HoloPazaak

A PyQt5/PyQt6 implementation of the Pazaak card game from Knights of the Old Republic.

## Requirements

- Python 3.8+

## Local Run

**With uv** (from PyKotor repo root):

```bash
uvx --with-editable Libraries/PyKotor --with-editable Tools/HoloPazaak holopazaak
# or: uv run --directory Tools/HoloPazaak/src --module holopazaak
```

**Without uv** (activated venv, from `Tools/HoloPazaak`):

### Windows

```powershell
python -m pip install -r requirements.txt
$env:PYTHONPATH = "$(Get-Location)\src"
python src/holopazaak/app.py
```

### Unix

```bash
python3 -m pip install -r requirements.txt
PYTHONPATH=$PWD/src python3 src/holopazaak/app.py
```

## Local Development

- Clone [PyKotor](https://github.com/OldRepublicDevs/PyKotor) and run the `install_python_venv.ps1` script in your powershell terminal. That's it!

## Building

To build the executable:

```powershell
./Tools/HoloPazaak/compile/build.ps1
```

The output will be in `dist/HoloPazaak/`.

