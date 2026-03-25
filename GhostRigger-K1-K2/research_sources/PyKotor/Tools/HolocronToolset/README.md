# HolocronToolset

A PyQt/PySide application that can edit the files used by the KotOR game engine.

## Requirements

- Python 3.8+
- qtpy (abstraction layer for pyqt5/6 and pyside2/6)
- (Optional) A KotOR I or II game installed on your machine somewhere.

## Local Run

**With uv** (from PyKotor repo root):

```bash
# End users (latest from PyPI)
uvx --refresh holocrontoolset

# Developers (local source)
uvx --with-editable Libraries/PyKotor --with-editable Tools/HolocronToolset holocrontoolset
uv run --directory Tools/HolocronToolset/src --module toolset
```

**Without uv** (activated venv, from `Tools/HolocronToolset`):

### Windows

```powershell
python -m pip install -r requirements.txt
$env:PYTHONPATH = (Get-Location).Path
python toolset/__main__.py
```

### Unix

```bash
python3 -m pip install -r requirements.txt
PYTHONPATH=$PWD python3 toolset/__main__.py
```

### Note for Alpine users:
You might get this error:
```
pyproject.toml: line 7: using '[tool.sip.metadata]' to specify the project metadata is deprecated and will be removed in SIP v7.0.0, use '[project]' instead
```
While we're not sure what the exact problem is, it seems newer python versions won't correctly be able to build pyqt5. If you don't have a binary available (--only-binary=:all: returns no versions) you'll need to downgrade python preferably to 3.8 or you won't be able to use qt5!
[See this issue for more information](https://github.com/altendky/pyqt-tools/issues/100)

## Local Development

- Clone [PyKotor](https://github.com/OldRepublicDevs/PyKotor). Use `uvx --with-editable` to run from local source, or run `install_python_venv.ps1` for a traditional venv setup.

## Accessing the GUI Designer

```bash
python -m pip install qt5-applications
```

Then navigate to your Python's site-packages folder:

```bash
python -m site --user-site
```

Then navigate to ```./site-packages/qt5_applications/Qt/bin``` and open the ```designer.exe``` file.
