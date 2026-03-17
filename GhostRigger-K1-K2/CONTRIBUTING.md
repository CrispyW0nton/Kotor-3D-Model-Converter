# Contributing to GhostRigger

Thanks for your interest in contributing! GhostRigger is a community modding tool and we welcome contributions of all kinds — bug reports, format research, code, tests, and documentation.

---

## Ways to Contribute

### 🐛 Bug Reports
Open a GitHub issue with:
- A minimal reproducible example (e.g., which MDL file triggers the bug)
- Expected vs. actual behaviour
- Python version and OS

### 📖 Format Research
If you've reverse-engineered something new about the KotOR MDL/MDX/TPC/GFF formats, please share it! Open an issue or PR with your findings. Reference sources (xoreos, KotorBlender, MDLOps, game files) whenever possible.

### 💻 Code Contributions

#### Setup
```bash
git clone https://github.com/<your-fork>/GhostRigger-K1-K2.git
cd GhostRigger-K1-K2
pip install -r requirements.txt
pip install pytest
pytest tests/          # all tests should pass before you start
```

#### Branch naming
```
feature/your-feature-name
fix/what-you-are-fixing
research/format-topic
```

#### Coding style
- Python 3.10+, standard library preferred
- No third-party dependencies in `src/core/` (the core library must be importable without PyOpenGL/Pillow)
- Type hints on public functions
- `struct.pack`/`struct.unpack` for binary I/O — no external binary parsing libs
- Keep the hot paths (parser inner loops) allocation-friendly

#### Tests
Every code change should have corresponding tests in `tests/`. Run the suite before opening a PR:
```bash
pytest tests/ -q
```
Tests must not depend on game files; skip gracefully with `pytest.skip()` if `KOTOR_K1_DIR` / `KOTOR_K2_DIR` are not set.

#### Pull Requests
- Target the `main` branch
- Include a short description of what changed and why
- Link to any relevant issues or format research
- Tests must pass

---

## Project Areas

| Area | Files | Notes |
|------|-------|-------|
| Binary MDL/MDX parser | `src/core/mdl_parser.py` | Largest file; heavily tested |
| Binary writer + K1↔K2 porter | `src/core/mdl_porter.py` | Round-trip correctness is critical |
| Model data classes | `src/core/model_data.py` | Adding fields needs parser + writer updates |
| Animation engine | `src/core/animation_engine.py` | SLERP, keyframe lerp |
| 3D viewport | `src/gui/viewport.py` | Software rasterizer; large file |
| Texture pipeline | `src/gui/viewport.py` | TPC/TXI/TGA decoding |
| Game archive reader | `src/core/game_library_ext.py` | KEY/BIF/ERF/RIM |
| GFF reader/writer | `src/formats/gff_*.py` | UTC, UTI, DLG, etc. |
| Auto-rigger | `src/autorig/` | Humanoid + creature skeletons |

---

## Format References

These are the authoritative sources we cross-check against:

- **[KotorBlender](https://github.com/seedhartha/kotorblender)** — most authoritative for binary MDL format details
- **[xoreos](https://github.com/xoreos/xoreos)** — open-source KotOR engine; `model_kotor.cpp` for controller types
- **[PyKotor / HolocronToolset](https://github.com/NickHugi/PyKotor)** — Python KotOR library; cross-reference for format decisions
- **[MDLOps](https://github.com/ndixUR/mdlops)** — original Perl MDL tool
- **[DeadlyStream](https://deadlystream.com)** — community modding forum with format research threads

---

## Code of Conduct

Be kind. This is a fan project made by modders for modders. Disagreements about format interpretations happen — cite your sources and we'll figure it out.
