# GhostRigger Native Visual Studio Wrapper

Open `GhostRigger.sln` from the repository root in Visual Studio 2022.

The first native project is a small C++ launcher. It keeps the current Python/Qt
application usable from Visual Studio while establishing a native project layout
for future graphics-heavy C++ work.

Build `GhostRiggerNative`, then run it from Visual Studio. With no arguments it
launches:

```powershell
python main.py --gui qt
```

Set `GHOSTRIGGER_PYTHON` if Visual Studio should use a specific interpreter:

```powershell
$env:GHOSTRIGGER_PYTHON = "C:\Path\To\python.exe"
```

Any command-line arguments passed to `GhostRiggerNative.exe` are forwarded to
`main.py`, replacing the default `--gui qt`.
