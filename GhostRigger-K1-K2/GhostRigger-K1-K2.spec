# -*- mode: python ; coding: utf-8 -*-
# GhostRigger-K1-K2.spec  —  PyInstaller build spec
# Generated: 2026-03-18
# Build:  python -m PyInstaller GhostRigger-K1-K2.spec --clean --noconfirm

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

# ── Data files ────────────────────────────────────────────────────────────
datas = [
    # Bundle the entire assets folder (icons, etc.)
    ('assets', 'assets'),
]

# ── Analysis ──────────────────────────────────────────────────────────────
a = Analysis(
    ['main.py'],
    pathex=['.'],
    binaries=[],
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
