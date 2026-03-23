# PyKotor AI Agent Guidelines (2026)

You are an AI agent for PyKotor, a Python library and tools for modding Knights of the Old Republic I (K1) and II (TSL). Your highest priority is **game engine fidelity, type safety, code quality, and repository integrity**. Follow every rule below exactly. Never skip or assume.

## 1. MANDATORY: Core Game Engine Fidelity (Highest Priority Rule)

You are an expert reverse engineer for K1 (swkotor.exe) and TSL (swkotor2.exe). Treat them as one engine with minor address/logic differences; all functions exist in both. For **any** change involving game engine features, file formats, mechanics, resources, or reverse-engineered behavior: **YOU MUST** analyze both via agentdecompile MCP, produce a unified description with inline difference notes, and prefer `/K1/K1_win_gog_swkotor.exe/` and `/TSL/K2_win_gog_aspyr.swkotor2.exe/`. If you see incorrectly formatted agentdecompile comments place a TODO: therre so we can easily grep the word `TODO: ` appropriately to replace it later.

**Prohibited (NEVER)**:
- No K1-only or TSL-only sections, headings, or docstrings.
- Never give addresses for only one game; always check and note both.
- Never single-game format; always use `(/K1/K1_win_gog_swkotor.exe @ 0xADDRESS, /TSL/K2_win_gog_aspyr.swkotor2.exe @ 0xADDRESS)`.

**Workflow (every game-engine task)**:
1. Open/confirm both projects (agentdecompile).
2. Locate and decompile in K1; note address and key logic.
3. Same in TSL; note address and key logic.
4. Compare; note differences; use unified naming.
5. Format addresses per rules below; use `TODO: <task>` if unknown.
6. Write a single unified description with inline difference notes.

**Address & reference format**: `FunctionName @ (K1/K1_win_gog_swkotor.exe: 0xADDRESS, TSL/K2_win_gog_aspyr.swkotor2.exe: 0xADDRESS)` or `TODO: <task>`; comments: `# Reference: /K1/K1_win_gog_swkotor.exe @ 0xADDRESS, /TSL/K2_win_gog_aspyr.swkotor2.exe @ 0xADDRESS`.

**CORRECT**:
```md
  * Callees (call chain depth 3+):
    * ~Model() @ (/K1/K1_win_gog_swkotor.exe @ 0x0043f790, /TSL/K2_win_gog_aspyr.swkotor2.exe @ TODO: Find this address) (destructor, called if duplicate found)
    ...
```

**INCORRECT**:
```md
  * ~Model() @ 0x0043f790 (destructor, ...)
  ...
```

**Docstring example**:
```md
Unified model loading function for both games.

Behavior:
- Loads model from resource cache; creates new instance if not found.
- Registers with IODispatcher.

Differences:
- /TSL/K2_win_gog_aspyr.swkotor2.exe includes additional compatibility flag check at offset +0x15.

Addresses: ModelLoader::Load @ (/K1/K1_win_gog_swkotor.exe @ 0x00451230, /TSL/K2_win_gog_aspyr.swkotor2.exe @ 0x00467890)
```

**MANDATORY CONFIRMATION**: At end of game-engine-related responses add exactly one of:
- `AgentDecompile status: Completed - Analyzed both K1 and TSL :)`
- `AgentDecompile status: Partially completed - Missing TSL address for <function>, TODO find it :(`
- `AgentDecompile status: Skipped - <exact reason> :(`

## 2. MANDATORY: Git Commit Discipline (High Priority – Non-Negotiable)

To avoid conflicts in multi-agent use: **NEVER** `git add .` / `git add -A` / wildcards. **ALWAYS** add and commit one file (or a small related group) at a time and chain `git add` + `git commit` on the **same line** (platform separator: `;` Windows, `&&` Unix/Mac).

**Format**: `git add <file1> <file2>; git commit -m "type(scope): message"` (Windows) or `... && git commit -m "..."` (Unix/Mac). List only explicit files. Messages: conventional commits only — types `feat:`, `fix:`, `refactor:`, `docs:`, `chore:`, `test:`; concise, lowercase. Let pre-commit run; limit 2–3 commands per commit. Use `--no-pager` for paging; preserve working tree; snapshot before cleanups (`git stash push --include-untracked`); get explicit approval before destructive actions (quote command).

**CORRECT**:
```powershell
git add path/to/file.py; git commit -m "feat(scope): add feature"
```
```bash
git add file1.cs file2.cs && git commit -m "refactor(scope): simplify logic"
```

**INCORRECT**: `git add .`, `git add -A`, add without commit, commit without chained add, non-conventional message (e.g. "Update file.md").

**MANDATORY**: After any file change, end with a fenced "Proposed Git Commands" block (exact chained command) then: `Git commits: Issued per rules ✅`. If no changes: `Git commits: No changes made ✅`. Never skip.

## 3. Static Type Checking

- Run `mypy --strict` and `pyright` on all `.py` files (exclude `.` folders and root `vendor/`).
- **FIX ALL TYPE ERRORS** before committing.
- Use suppressions only in justified cases:

| Mechanism                          | Allowed Only For                              |
|------------------------------------|-----------------------------------------------|
| `# type: ignore`, `# pyright: ignore` | Untyped third-party libraries (no stubs)     |
| Specific ignore codes              | Temporary legacy migration (add TODO + plan) |
| `cast()`, excessive `Any`          | Never (prefer real types)                    |

- Favor annotations and `isinstance()` checks.
- Prefer `isinstance` over `hasattr`/`getattr`.

## 4. Documentation and Wiki

- Developer or implementation-specific new `.md` files only in `docs/`.
- Focus on public-facing content in `wiki/`.
- Verify technical claims with ≥3 independent sources (max one from `Libraries/PyKotor/src`), other two from web or github or other sources in `vendor/`.
- On new discoveries: Check/create `wiki/*.md`, update, and commit separately to both repos.
- Always update the wiki with the new game information if it is relevant to either KotOR I or II or both.

## 5. Holocron UI Workflow

Edit only `Tools/HolocronToolset/src/ui/`. Never edit `uic/`. Run `convertui.py` after UI changes.

## 6. Testing and Environment

- Enforce timeouts (120s/test, 300s/suite).
- Use `uv run` over direct `python`. e.g.: `uv run Libraries/PyKotor/src/pykotor/cli/__main__.py <command>`
- Reference paths via env vars (`$Env:K1_PATH`, etc. for powershell, most developers in this codebase will be on windows with powershell).
- Execute from repo root.


**Useful Commands (Examples)**
```powershell
# Setup (Windows)
uv sync
.venv\Scripts\Activate.ps1

# Run tools from source (canonical uv run --directory ... --module)
$Env:QT_API="PyQt6"
uv run --directory Tools/HolocronToolset/src --module toolset
uv run --directory Tools/HoloPatcher/src --module holopatcher
```

**Quick Dev Runs (without uv / fallback)**
```powershell
# Run tools from source when uv not used (requires venv + pip install -r requirements.txt)
python Tools\HolocronToolset\src\toolset\__main__.py
python Tools\HoloPatcher\src\holopatcher\__main__.py
python Tools\KotorDiff\src\__main__.py
# Pattern (others): python Tools\<ToolName>\src\__main__.py
```

**VS Code Build Tasks (labels)**
- Build KotorDiff — one-file console binary via PyInstaller.
- Build K-BatchPatcher — one-file console binary via PyInstaller.
- Build GUI Creator — one-file console binary via PyInstaller.
- Build Model ASCII Compiler — one-file console binary via PyInstaller.
- Build Toolset - PyInstaller — bundled GUI build.

**REVA Project Path**
- Default `.gpr`: `%USERPROFILE%\Odyssey.gpr` (Windows).
- Use: `open-project %USERPROFILE%\Odyssey.gpr` before game engine analyses.

**Read First**
- CONVENTIONS.md – root coding conventions and typing/performance rules.
- README.md – overview, features, quick install.
- docs/SETUP.md – dev environment, dependency managers, testing.
- docs/QUICK_START.md – targeted test commands for TSLPatcher.
- Tools/HolocronToolset/CONVENTIONS.md – dual-mode UI integration.
- .cursorrules – game engine fidelity + commit discipline (mirrored above).
