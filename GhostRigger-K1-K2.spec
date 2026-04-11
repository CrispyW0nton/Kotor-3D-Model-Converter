# -*- mode: python ; coding: utf-8 -*-
# GhostRigger-K1-K2.spec  —  PyInstaller build spec
# Generated: 2026-03-18
# Build:  python -m PyInstaller GhostRigger-K1-K2.spec --clean --noconfirm

import os
import sys
from PyInstaller.utils.hooks import collect_submodules, collect_data_files

# ── Hidden imports ────────────────────────────────────────────────────────
# tkinter and its sub-modules are not auto-detected on all platforms
hiddenimports = [
    'tkinter',
    'tkinter.ttk',
    'tkinter.filedialog',
    'tkinter.messagebox',
    'tkinter.colorchooser',
    'PIL._tkinter_finder',
]

# Collect every sub-module under src/ so dynamic imports (gui, ipc, kotormcp, etc.) work
hiddenimports += collect_submodules('src')

# Optional GPU path — include if present, silently skip if not installed
try:
    import moderngl  # noqa: F401
    hiddenimports += collect_submodules('moderngl')
except ImportError:
    pass

try:
    import numpy  # noqa: F401
    hiddenimports += ['numpy', 'numpy.core', 'numpy.lib']
except ImportError:
    pass

# ── Assimp DLL bundling (optional) ───────────────────────────────────────
# pyassimp searches its own package folder for any file whose name contains
# 'assimp', so we bundle the DLL as a binary alongside pyassimp's package.
# build.bat downloads the DLL and places it there before running this spec.
# If pyassimp is not importable (e.g. Python 3.14 C-extension not yet built),
# we skip it entirely and add it to excludes so PyInstaller doesn't crash.
binaries = []
_pyassimp_available = False
try:
    import pyassimp as _pa
    _pa_dir = os.path.dirname(_pa.__file__)
    for _fname in os.listdir(_pa_dir):
        if 'assimp' in _fname.lower() and _fname.lower().endswith('.dll'):
            _dll_path = os.path.join(_pa_dir, _fname)
            binaries.append((_dll_path, 'pyassimp'))
            print(f'[spec] Bundling Assimp DLL: {_dll_path}')
            _pyassimp_available = True
            break
    else:
        print('[spec] WARNING: No assimp*.dll found in pyassimp folder — '
              'FBX import will be unavailable at runtime.')
except Exception:
    print('[spec] pyassimp not importable — excluding from build. '
          'FBX import will be unavailable (all other features unaffected).')

# ── Data files ────────────────────────────────────────────────────────────
datas = [
    # Bundle the entire assets folder (icons, etc.)
    ('assets', 'assets'),
]

# ── Analysis ──────────────────────────────────────────────────────────────
a = Analysis(
    ['main.py'],
    pathex=['.'],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # Keep the exe lean — these are server-side / CI-only deps
        'pytest',
        'unittest',
        'pydantic',
        'mcp',
        # Exclude pyassimp if it couldn't be imported (e.g. Python 3.14)
        # so PyInstaller doesn't crash trying to analyse it
        *( [] if _pyassimp_available else ['pyassimp'] ),
    ],
    noarchive=False,
    optimize=0,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name='GhostRigger-K1-K2',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,                          # no console window on Windows
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon='assets/icons/ghostrigger.ico',    # Windows taskbar / exe icon
)
