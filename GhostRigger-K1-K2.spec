# -*- mode: python ; coding: utf-8 -*-
# GhostRigger-K1-K2.spec  —  PyInstaller build spec
# Generated: 2026-03-18
# Build:  python -m PyInstaller GhostRigger-K1-K2.spec --clean --noconfirm

import os
import sys
from PyInstaller.utils.hooks import collect_submodules, collect_data_files

_NATIVE_PYTHON_ROOTS = []
_native_dir = os.path.join(os.getcwd(), 'native')
if os.path.isdir(_native_dir):
    for _project_name in sorted(os.listdir(_native_dir)):
        _python_root = os.path.join(_native_dir, _project_name, 'Python')
        if os.path.isdir(os.path.join(_python_root, 'src')):
            _NATIVE_PYTHON_ROOTS.append(_python_root)

for _python_root in reversed(_NATIVE_PYTHON_ROOTS):
    if _python_root not in sys.path:
        sys.path.insert(0, _python_root)

# ── Hidden imports ────────────────────────────────────────────────────────
# M3/T304 — Qt is the only supported front-end. The previous tkinter +
# PIL._tkinter_finder hidden-imports block was removed when the Tk
# launcher was deleted in M3/T302+T303.
hiddenimports = [
    'PySide6',
    'PySide6.QtCore',
    'PySide6.QtGui',
    'PySide6.QtWidgets',
]

# Collect every sub-module under src/ individually so a single broken
# sub-package (e.g. src.kotormcp.utils which imports bare 'kotormcp')
# doesn't abort the entire collection.
for _pkg in [
    'src',
    'src.core',
    'src.gui',
    'src.ipc',
    'src.converters',
    'src.autorig',
    'src.formats',
    'src.resources',
    'src.kotormcp',
]:
    try:
        hiddenimports += collect_submodules(_pkg)
    except Exception as _e:
        print(f'[spec] WARNING: collect_submodules({_pkg!r}) skipped: {_e}')

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

try:
    import PySide6  # noqa: F401
    hiddenimports += collect_submodules('PySide6')
except ImportError:
    pass

# ── Assimp DLL bundling (optional) ───────────────────────────────────────
# Priority 1: pyassimp + native DLL → full bone/skin FBX import
# Priority 2: assimp_py (bundles native lib in wheel) → geometry-only FBX import
# build.bat downloads the DLL and places it in pyassimp's folder before this spec.
# If neither is importable, we exclude them so PyInstaller doesn't crash.
binaries = []
_pyassimp_available = False
_assimp_py_available = False

# Check pyassimp + its DLL
try:
    import importlib.util as _ilu
    _pa_spec = _ilu.find_spec('pyassimp')
    if _pa_spec is not None:
        _pa_dir = os.path.dirname(_pa_spec.origin)
        for _fname in os.listdir(_pa_dir):
            if 'assimp' in _fname.lower() and _fname.lower().endswith('.dll'):
                _dll_path = os.path.join(_pa_dir, _fname)
                binaries.append((_dll_path, 'pyassimp'))
                print(f'[spec] Bundling Assimp DLL: {_dll_path}')
                _pyassimp_available = True
                break
        else:
            print('[spec] WARNING: No assimp*.dll found in pyassimp folder — '
                  'pyassimp bone import unavailable.')
    else:
        print('[spec] pyassimp not installed.')
except BaseException as _e:
    print(f'[spec] pyassimp check failed ({_e}) — excluding from build.')

# Check assimp_py (geometry-only fallback, bundles its own native lib)
try:
    _ap_spec = _ilu.find_spec('assimp_py')
    if _ap_spec is not None:
        _assimp_py_available = True
        # assimp_py bundles the native lib inside its wheel — collect its binaries
        _ap_origin = _ap_spec.origin
        if _ap_origin:
            _ap_dir = os.path.dirname(_ap_origin)
            for _fname in os.listdir(_ap_dir):
                _fl = _fname.lower()
                if ('assimp' in _fl) and (_fl.endswith('.dll') or _fl.endswith('.so') or _fl.endswith('.pyd')):
                    _dll_path = os.path.join(_ap_dir, _fname)
                    binaries.append((_dll_path, 'assimp_py'))
                    print(f'[spec] Bundling assimp_py binary: {_dll_path}')
        print('[spec] assimp_py available (geometry-only FBX fallback).')
    else:
        print('[spec] assimp_py not installed.')
except BaseException as _e:
    print(f'[spec] assimp_py check failed ({_e}).')

if _pyassimp_available:
    print('[spec] FBX import: FULL (pyassimp with bone/skin data)')
elif _assimp_py_available:
    print('[spec] FBX import: GEOMETRY ONLY (assimp_py, no bone data)')
else:
    print('[spec] FBX import: DISABLED (neither pyassimp nor assimp_py available)')

# ── Data files ────────────────────────────────────────────────────────────
datas = [
    # Bundle app assets plus GUI resources loaded by package-relative paths.
    ('assets', 'assets'),
    ('config', 'config'),
    ('knowledge_base/retargeting', 'knowledge_base/retargeting'),
    ('scripts', 'scripts'),
    ('src/gui/icons', 'src/gui/icons'),
    ('src/gui/fonts', 'src/gui/fonts'),
    ('src/systems/bas/models', 'src/systems/bas/models'),
]

# ── Analysis ──────────────────────────────────────────────────────────────
a = Analysis(
    ['native/GhostRigger.Native.Core.Host/main.py'],
    pathex=['.', *_NATIVE_PYTHON_ROOTS],
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
        # M3/T304 — actively exclude tkinter so PyInstaller doesn't auto-pull
        # the stdlib Tcl/Tk runtime into the bundle (~5-10 MB on Windows).
        # GhostRigger no longer imports tkinter from any module.
        'tkinter',
        'tkinter.ttk',
        'tkinter.filedialog',
        'tkinter.messagebox',
        'tkinter.colorchooser',
        'PIL._tkinter_finder',
        # Exclude assimp libs if not importable so PyInstaller doesn't crash
        *( [] if _pyassimp_available else ['pyassimp'] ),
        *( [] if _assimp_py_available else ['assimp_py'] ),
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
