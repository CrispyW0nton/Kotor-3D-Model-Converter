# KotorDiff Integration in PyKotor CLI

The standalone KotorDiff tool now ships inside PyKotor CLI and follows the same headless-first pattern as other Holocron utilities.

## Behavior

- Supplying any diff paths keeps execution headless; omitting paths or passing `--gui` launches the Tkinter UI (`Libraries/PyKotor/src/pykotor/diff_tool/__main__.py` L20-L120).
- CLI arguments are shared between the dedicated scripts (`kotordiff`, `kotordiff`, `diff`) and the `pykotorcli diff` subcommand (`Libraries/PyKotor/src/pykotor/diff_tool/cli.py` L26-L147).
- Headless execution builds a `KotorDiffConfig` and routes to the n-way differ (`Libraries/PyKotor/src/pykotor/diff_tool/cli.py` L168-L238).

## CLI Usage

```bash
# Installation vs installation with filtering
pykotorcli diff --path1 "C:\Games\KOTOR" --path2 "C:\Games\KOTOR_Modded" --filter tat_m17ac --output-mode normal

# Generate incremental TSLPatcher output while diffing
pykotorcli diff "C:\Games\KOTOR" "C:\Games\KOTOR_Modded" --tslpatchdata .\tslpatchdata --ini changes.ini --incremental

# Compare specific container m13ab.rim with the composite rim module m13ab.
pykotorcli diff "D:\workspace\Ajunta_Paul\m13ab.rim" "C:\Program Files (x86)\Steam\steamapps\common\swkotor\Modules\m13ab"

# Compare composite module danm13 with an entire installation
pykotorcli diff "D:\workspace\Dantooine_Modifications\danm13" "C:\Program Files (x86)\Steam\steamapps\common\swkotor"

# Compare installation with basic folder (compares folder including subfolders, with the installation respecting its resolution order)
pykotorcli diff "C:\Program Files (x86)\Steam\steamapps\common\swkotor" "D:\workspace\folder_with_various_gffs_2das_etc\"
```

[KEY](KEY-File-Format) flags:

- `--path1/--path2/--path3/--path` for multi-path comparisons
- `--filter` to constrain resources/modules
- `--output-mode` (`full`, `normal`, `quiet`) + `--output-log`
- `--tslpatchdata` / `--ini` with optional `--incremental` writer
- `--compare-hashes/--no-compare-hashes`, `--log-level`, `--no-color`, `--use-profiler`, `--gui`

## Implementation Notes

- Diff orchestration, filtering, and incremental TSLPatcher generation live in `[Libraries/PyKotor/src/pykotor/diff_tool/app.py](https://github.com/OldRepublicDevs/PyKotor/tree/master/Libraries/PyKotor/src/pykotor/diff_tool/app.py)` L40-L530. Incremental writer creation and [StrRef](TLK-File-Format#string-references-strref) analysis are handled in `handle_diff` and `generate_tslpatcher_data` (L295-L529).
- CLI argument wiring and headless execution are defined in `[Libraries/PyKotor/src/pykotor/diff_tool/cli.py](https://github.com/OldRepublicDevs/PyKotor/tree/master/Libraries/PyKotor/src/pykotor/diff_tool/cli.py)` L26-L238.
- [GUI](GFF-File-Format#gui-graphical-user-interface) fallback is implemented in `[Libraries/PyKotor/src/pykotor/diff_tool/gui.py](https://github.com/OldRepublicDevs/PyKotor/tree/master/Libraries/PyKotor/src/pykotor/diff_tool/gui.py)` (headless when arguments are present, UI when omitted).
