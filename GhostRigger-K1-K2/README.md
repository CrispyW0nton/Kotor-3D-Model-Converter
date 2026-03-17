# GhostRigger

**A KotOR modding pipeline tool for Star Wars: Knights of the Old Republic 1 & 2 (TSL)**

GhostRigger is an open-source Python tool for working with KotOR's Odyssey Engine model format (MDL/MDX). It can parse, visualize, modify, and cross-port 3D models between KotOR 1 and KotOR 2 — entirely in Python, no game installation required for the core library.

---

## What It Does

| Feature | Status |
|---|---|
| Binary MDL/MDX parser (K1 + K2/TSL) | ✅ Complete |
| ASCII MDL parser + writer | ✅ Complete |
| Binary MDL writer (K1 ↔ K2 round-trip) | ✅ Complete |
| K1 ↔ K2 cross-game porter | ✅ Complete |
| Animation engine (keyframe interpolation, SLERP) | ✅ Complete |
| UV pipeline (seam-fix, tiling, multi-layer UVs) | ✅ Complete |
| LBS skinning (linear blend skinning, bone weights) | ✅ Complete |
| TPC/TPA texture loading | ✅ Complete |
| 3D viewport (software rasterizer, textures, bones) | ✅ Complete |
| Game library browser (KEY/BIF/ERF/RIM archives) | ✅ Complete |
| OBJ/FBX import & export | ✅ Complete |
| Auto-rigger (humanoid & creature skeletons) | ✅ Complete |
| GFF reader/writer (UTC, UTI, DLG, etc.) | ✅ Complete |
| 2DA reader/writer | ✅ Complete |
| MDX multi-UV channel support (UV1–UV4 + tangent space) | ✅ Complete |

---

## Quick Start

### Requirements
- Python 3.10+
- `pip install Pillow numpy PyOpenGL PyOpenGL_accelerate`
- Optional: `pyassimp` for FBX support

### Run the GUI
```bash
python main.py
```

### Point to your game directories
In the **Library** panel, click **Set K1 Dir** / **Set K2 Dir** and point to your KotOR installation folder, e.g.:
- Windows: `C:\Program Files (x86)\Steam\steamapps\common\swkotor`
- Linux: `~/.steam/steam/steamapps/common/swkotor`

Or set environment variables:
```bash
export KOTOR_K1_DIR=/path/to/swkotor
export KOTOR_K2_DIR=/path/to/swkotor2
```

### Use the core library (no GUI)
```python
from src.core.mdl_parser import MDLBinaryParser
from src.core.mdl_porter import CrossGamePorter, MDLBinaryWriter

# Parse a model
model = MDLBinaryParser.parse_files('c_bantha.mdl', 'c_bantha.mdx')
print(f"Model: {model.name}, nodes: {len(list(model.all_nodes()))}")

# Port K1 → K2
k2_model = CrossGamePorter().port(model, target_game='K2')

# Write binary output
MDLBinaryWriter().write(k2_model, 'c_bantha_k2.mdl', 'c_bantha_k2.mdx')
```

---

## Windows EXE Build
```
double-click build.bat
```
Produces `dist/GhostRigger-K1-K2.exe` (portable, no Python install needed).

---

## Project Structure

```
src/
  core/
    mdl_parser.py       — Binary + ASCII MDL/MDX parser
    mdl_porter.py       — Binary writer + K1↔K2 cross-porter
    model_data.py       — KotorModel / ModelNode data classes
    animation_engine.py — Keyframe interpolation + pose evaluation
    game_library_ext.py — KEY/BIF/ERF/RIM archive reader
    twoda.py            — 2DA format reader/writer
    module_format.py    — LYT/VIS/GFF module format support
  gui/
    main_window.py      — Main application window
    viewport.py         — 3D software rasterizer viewport
    blueprint_editor.py — UV/blueprint editor panel
    tex_atlas.py        — Texture atlas builder
  autorig/
    auto_rigger.py      — Automatic bone weight assignment
    cloth_rig.py        — Cloth/PBD physics simulation
  converters/
    mesh_converter.py   — OBJ/FBX import/export
    normal_map.py       — Normal map generation
  formats/
    gff_reader.py       — GFF binary format reader
    gff_writer.py       — GFF binary format writer

tests/                  — 2200+ unit tests
tools/                  — Batch audit and render scripts
scripts/                — Standalone analysis scripts
test_assets/            — Sample MDL/MDX/TGA files for tests
devlog/                 — Development notes and research writeups
```

---

## MDL/MDX Format Notes

GhostRigger implements a from-scratch binary MDL/MDX parser based on research from:
- [xoreos](https://github.com/xoreos/xoreos) — open-source KotOR engine reimplementation
- [KotorBlender](https://github.com/seedhartha/kotorblender) — Blender plugin for KotOR models
- [PyKotor / HolocronToolset](https://github.com/NickHugi/PyKotor) — Python KotOR library
- [MDLOps](https://github.com/ndixUR/mdlops) — community MDL tool
- Community research on [DeadlyStream](https://deadlystream.com)

See `RESEARCH_FINDINGS.md` for detailed format documentation.

### MDX Bitmap Flags
| Bit | Flag | Description |
|-----|------|-------------|
| 0x0001 | VERTEX | XYZ vertex positions (12 bytes) |
| 0x0002 | UV1 | Texture0 UV coords (8 bytes) |
| 0x0004 | UV2 | Texture1/lightmap UV (8 bytes) |
| 0x0008 | UV3 | Texture2 UV (8 bytes, rare) |
| 0x0010 | UV4 | Texture3 UV (8 bytes, rare) |
| 0x0020 | NORMAL | Vertex normals (12 bytes) |
| 0x0040 | COLOR | Vertex RGBA colors (4 bytes) |
| 0x0080 | TANGENT1 | Tangent-space Tex0 (36 bytes) |
| 0x0100 | TANGENT2 | Tangent-space Tex1 (36 bytes) |
| 0x0200 | TANGENT3 | Tangent-space Tex2 (36 bytes) |
| 0x0400 | TANGENT4 | Tangent-space Tex3 (36 bytes) |

---

## Running Tests
```bash
pip install pytest
pytest tests/
```

Tests run without game files. Tests that require game data skip automatically unless `KOTOR_K1_DIR` / `KOTOR_K2_DIR` are set.

---

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md).

Issues, PRs, and format research are all welcome. This project aims to be the most complete open-source Python implementation of the KotOR Odyssey Engine MDL/MDX pipeline.

---

## License

MIT License — see [LICENSE](LICENSE).

This tool is a fan-made modding utility. Star Wars: Knights of the Old Republic and The Sith Lords are property of LucasArts / Lucasfilm / Disney / Aspyr / Obsidian Entertainment. Game data files are not included in this repository.
