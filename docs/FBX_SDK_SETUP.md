# Autodesk FBX SDK Setup

Autodesk FBX SDK is an external optional dependency. GhostRigger does not bundle or redistribute Autodesk SDK files. You must download and install it separately under Autodesk's licence terms.

GhostRigger's FBX import/export feature stays disabled until the Autodesk Python FBX bindings are detected in the current Python environment.

## Official Source

Download Autodesk FBX SDK / Python bindings from Autodesk's official page:

https://aps.autodesk.com/developer/overview/fbx-sdk

Autodesk's Python FBX documentation describes the Python binding as a wrapper for the FBX SDK C++ library. It supports import/export options, scene hierarchy traversal, object inspection, properties, and file import/export.

## Check Your Python Runtime

Run these commands in the same Python environment used by GhostRigger:

```powershell
python --version
python -c "import platform, struct; print(platform.platform()); print(struct.calcsize('P') * 8)"
python -c "import fbx; print('FBX OK')"
```

The Autodesk FBX Python binding must match your Python ABI and architecture. For example, a binding built for Python 3.11 64-bit usually will not import in Python 3.13 64-bit.

## Configure GhostRigger

1. Open `Tools > Setup > Autodesk FBX SDK Setup...`.
2. Read the external dependency notice.
3. Use `Open Autodesk FBX SDK Download Page` to open Autodesk's official download page.
4. Download and install/extract the SDK using Autodesk's licence flow.
5. Select the local SDK root, the folder containing `fbx.pyd`/`fbx.so`, and the folder containing `FbxCommon.py`.
6. Click `Test Selected Path`.
7. Click `Save Configuration` only after the test succeeds.

GhostRigger stores only paths in `settings.json` under `fbx_sdk`. It does not copy Autodesk files into the repository or application folders.

## If Your Python Version Is Unsupported

Autodesk's older documentation references Python 2.6 and Python 3.1-era bindings. Modern Autodesk SDK releases may support different Python versions. If Autodesk does not provide bindings for GhostRigger's current Python version, use a Python version supported by the Autodesk FBX Python SDK available to you, or configure a dedicated GhostRigger Python environment.

Do not install unofficial FBX packages as the default solution unless the project owner explicitly approves that route. GhostRigger expects Autodesk's `fbx` module and optionally `FbxCommon.py`.

## Troubleshooting

Run:

```powershell
python scripts/print_fbx_python_environment.py
```

This prints Python version, executable, architecture, `sys.path`, import status for `fbx` and `FbxCommon`, and the configured GhostRigger FBX SDK paths.

Common failures:

- `No module named 'fbx'`: choose the folder containing Autodesk's Python binding binary.
- DLL/shared-library load error: add the SDK binary/library folder for the same platform and architecture.
- Wrong architecture or ABI error: choose bindings matching the exact Python major/minor version and 32-bit/64-bit architecture.

