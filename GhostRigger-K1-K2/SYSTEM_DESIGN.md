# Ghostworks Pipeline — System Design Document
## v3.4.1 ✔ Completed | v3.5 Planning Edition

> **Theoretical basis**:
> - *Structured Design* — Yourdon & Constantine (1979) [coupling, cohesion, transform analysis]
> - *Balancing Coupling in Software Design* — Vlad Khononov (2024) [contract coupling, volatility]

> **Monorepo**: [OldRepublicDevs/PyKotor](https://github.com/OldRepublicDevs/PyKotor)
> GhostScripter, GModular, GhostRigger, KotorMCP, HolocronToolset live as git submodules under `Tools/`

---

## 1. Ecosystem Map

The Ghostworks pipeline is **one subsystem inside the larger OldRepublicDevs/PyKotor monorepo**. Understanding the full ecosystem is required for compliant design decisions.

```
OldRepublicDevs/PyKotor  (monorepo)
├── Libraries/
│   └── PyKotor/               ← THE authoritative KotOR Python library
│       └── pykotor/           ← All binary parsers live here
│
└── Tools/
    ├── KotorMCP/              ← UPSTREAM MCP server (OldRepublicDevs-owned)
    │   └── src/kotormcp/      ← 25 tools, mcp-native (types.Tool), clean arch
    │
    ├── HolocronToolset/       ← FULL desktop editor (PyQt5, hundreds of editors)
    │   └── src/toolset/       ← NCS compiler/decompiler, all format editors
    │
    ├── GhostScripter-K1-K2/   ← OUR script/dialogue IDE (CrispyW0nton)
    │   └── ghostscripter/mcp/ ← 27 MCP tools, WRITES DLG/GFF, TSLPatcher output
    │
    ├── GModular/              ← OUR level/scene editor (CrispyW0nton)
    │   └── gmodular/ipc/      ← HTTP IPC :7003, NO MCP server yet
    │
    └── Kotor-3D-Model-Converter/  ← OUR model pipeline (CrispyW0nton)
        └── src/kotormcp/      ← GhostRigger's embedded MCP (34 tools)
```

---

## 2. The KotorMCP Alignment Problem

**GhostRigger currently vendors its own `src/kotormcp/` package** — a fork/extension of the upstream `OldRepublicDevs/KotorMCP`. This creates three divergence risks:

| Concern | Current State | Target State |
|---|---|---|
| `state.py` | GhostRigger has its own diverged copy | Use upstream `kotormcp.state` directly |
| `ports.py` / adapters | GhostRigger-specific abstraction layer | Keep — adds value absent from upstream |
| Tool naming | Mixed: camelCase + kotor_ prefix + ghostrigger_ prefix | Uniform `verb_noun` per convention |
| Upstream tool gaps in ours | Missing: refs, archives, walkmesh | Port from upstream |
| Our tools absent from upstream | `get_resource`, `get_quest`, decompile bridge | Submit upstream PRs or keep as extension |

### Upstream KotorMCP Tools (25)

| Tool Name | Module | Ours? |
|---|---|---|
| `detectInstallations` | installation | ✅ |
| `loadInstallation` | installation | ✅ |
| `kotor_installation_info` | installation | ✅ |
| `listResources` | discovery | ✅ |
| `describeResource` | discovery | ✅ |
| `kotor_find_resource` | discovery | ✅ |
| `kotor_search_resources` | discovery | ✅ |
| `kotor_read_gff` | conversion | ✅ (gffdata.py) |
| `kotor_read_2da` | conversion | ✅ (gffdata.py) |
| `kotor_read_tlk` | conversion | ✅ (gffdata.py) |
| `kotor_list_modules` | modules | ✅ |
| `kotor_describe_module` | modules | ✅ |
| `kotor_module_resources` | modules | ✅ |
| `kotor_list_archive` | archives | ✅ ported v3.4 |
| `kotor_extract_resource` | archives | ✅ ported v3.4 |
| `journalOverview` | gamedata | ✅ |
| `kotor_lookup_2da` | gamedata | ✅ |
| `kotor_lookup_tlk` | gamedata | ✅ |
| `kotor_list_references` | refs | ✅ ported v3.4 |
| `kotor_find_referrers` | refs | ✅ ported v3.4 |
| `kotor_find_strref_referrers` | refs | ✅ ported v3.4 |
| `kotor_describe_dlg` | refs | ✅ ported v3.4 |
| `kotor_describe_jrl` | refs | ✅ ported v3.4 |
| `kotor_describe_resource_refs` | refs | ✅ ported v3.4 |
| `kotor_walkmesh_validation_diagram` | walkmesh | ✅ ported v3.4 |

**All 25 upstream tools now present in GhostRigger** (9 were ported in v3.4).

### GhostRigger-Exclusive Tools (11 added)
| Tool Name | Module | Upstream? |
|---|---|---|
| `ghostrigger_open_model` | ghostrigger | ❌ GR only |
| `ghostrigger_render_model` | ghostrigger | ❌ GR only |
| `ghostrigger_model_info` | ghostrigger | ❌ GR only |
| `ghostrigger_list_game_models` | ghostrigger | ❌ GR only |
| `ghostrigger_audit` | ghostrigger | ❌ GR only |
| 11× `kotor_binary_*` | decompile | ❌ GR only (AgentDecompile) |
| `get_resource` | resource | ❌ GR only (v3.3) |
| `get_quest` | quest | ❌ GR only (v3.3) |

---

## 3. GhostScripter MCP: What It Has That We Don't

GhostScripter (our sibling tool) exposes **write-back tools** and **NWScript tools** over MCP that GhostRigger lacks:

| GhostScripter Tool | Capability | GhostRigger parity? |
|---|---|---|
| `writeDLG` | Writes dialogue binary | ❌ |
| `writeGFF` | Generic GFF write-back | ❌ |
| `readDLG` | DLG-specific structured reader | Partial (`kotor_read_gff`) |
| `compileSummary` | NWScript static analysis | ❌ |
| `nwscriptSignature` | Function signatures | ❌ |
| `twoDAChangesINI` | TSLPatcher diff generator | ❌ |
| `moduleOverview` | Area creature/item/door dump | Partial (`kotor_describe_module`) |

**Design principle (Constantine)**: GhostScripter and GhostRigger should NOT duplicate each other's tools. The correct architecture is: each exposes its own MCP server, and a client can connect to multiple servers (multi-server MCP). The `claude_desktop_config.json` pattern already supports this.

---

## 4. HolocronToolset: Merge Strategy

HolocronToolset is a **mature, full-featured PyQt5 desktop editor** with:
- All KotOR format editors (GFF, DLG, 2DA, TLK, TPC, MDL, ARE, GIT, UTx, etc.)
- NCS compiler + decompiler (wraps nwnnsscomp, NCSDecomp)  
- Blender IPC bridge
- Hundreds of editor widgets
- Existing test suite

**User's recommendation:**
> Rename HolocronToolset → HolocronToolset_old, rename your preferred base → HolocronToolset, use AI to merge relevant parts

### Merge Strategy (Constantine Transform Analysis)

```
HolocronToolset (upstream)          GhostRigger / GModular / GhostScripter (ours)
────────────────────────────         ──────────────────────────────────────────────
✅ NCS compiler/decompiler           ✅ GPU MDL renderer (unique)
✅ All format editors (PyQt5)        ✅ MCP server integration (unique)
✅ Blender bridge                    ✅ AgentDecompile/Ghidra bridge (unique)
✅ Large test suite                  ✅ IPC tri-tool protocol
✅ Module patcher                    ✅ KotorMCP tool extensions
✅ ERF/RIM/MOD packer                ✅ Ports & Adapters architecture
```

**Phase 1 — No-risk imports (add to GhostRigger, no GUI needed):**
- `HolocronToolset/src/toolset/utils/script_decompiler.py` → enables real NCS→NSS in `get_quest`
- `HolocronToolset/src/toolset/utils/script_compiler.py` → enables `compile_script` tool

**Phase 2 — GUI merge (GModular as new HolocronToolset base):**
- GModular has the superior architecture (ModernGL GPU renderer, MCP server, IPC)
- HolocronToolset has the superior format editor coverage (all UTx, DLG node editor, etc.)
- Merge target: GModular becomes the new `HolocronToolset` (per user directive)
- Preserve: all HolocronToolset format editors as panels in GModular's UI
- Preserve: GModular's `gmodular/ipc/` and add an MCP server to it

**Phase 3 — MCP unification:**
- Single `kotormcp` package (upstream KotorMCP as base)
- GhostRigger extensions live in `kotormcp_ghostrigger` extension module
- All tools follow the upstream `types.Tool` native API (not dict wrappers)

---

## 5. Current IPC Architecture (v3.4 accurate)

```
 ┌─────────────────────────────────────────────────────────────────────────┐
 │                         CONSUMER LAYER                                  │
 │                                                                         │
 │  Claude Desktop  Cursor/VS Code  Discord bot  CI pipeline  CLI agent   │
 │       │               │               │             │           │       │
 │    stdio MCP       HTTP MCP        HTTP MCP      stdio      stdio      │
 └───────┬───────────────┬───────────────┬────────────┴───────────┴───────┘
         │               │               │
 ┌───────▼───────────────▼───────────────▼───────────────────────────────┐
 │                       MCP SERVER LAYER                                 │
 │                                                                        │
 │  ┌─────────────────────────┐  ┌────────────────────────┐              │
 │  │   GhostRigger KotorMCP  │  │   GhostScripter MCP    │              │
 │  │   src/kotormcp/         │  │   ghostscripter/mcp/   │              │
 │  │   port 7001 + stdio     │  │   port 6400 + stdio    │              │
 │  │   34 tools              │  │   27 tools             │              │
 │  │   (upstream 17 + 17 GR) │  │   (upstream 10 + 17 GS)│              │
 │  └──────────┬──────────────┘  └────────────┬───────────┘              │
 │             │                              │                           │
 │  ┌──────────▼──────────────────────────────▼──────────────────────┐   │
 │  │        Upstream KotorMCP  (OldRepublicDevs)                    │   │
 │  │        Tools/KotorMCP/src/kotormcp/   25 tools                 │   │
 │  │        — canonical reference implementation                     │   │
 │  └────────────────────────────────────────────────────────────────┘   │
 └───────────────────────────────┬────────────────────────────────────────┘
                                 │
 ┌───────────────────────────────▼────────────────────────────────────────┐
 │                      CORE PIPELINE LAYER                               │
 │                                                                        │
 │  ┌─────────────┐  ┌─────────────────┐  ┌────────────────────────────┐ │
 │  │ GhostRigger │  │  GhostScripter  │  │        GModular            │ │
 │  │  :7001      │◄─┤    :7002        │  │        :7003               │ │
 │  │ MDL/MDX     │  │  NWScript IDE   │  │  Level editor / GFF        │ │
 │  │ GPU Render  │  │  DLG editor     │  │  Walkmesh / .mod export    │ │
 │  │ Rigging     │  │  Quest builder  │  │  ModernGL 3D scene         │ │
 │  └──────┬──────┘  └────────┬────────┘  └──────────┬─────────────────┘ │
 │         └─────────────────┴────────────────────────┘                  │
 │              IPC: HTTP POST JSON   (ports 7001 / 7002 / 7003)         │
 └───────────────────────────────┬────────────────────────────────────────┘
                                 │
 ┌───────────────────────────────▼────────────────────────────────────────┐
 │                        DATA LAYER                                      │
 │                                                                        │
 │  Libraries/PyKotor (OldRepublicDevs)     AgentDecompile / Ghidra      │
 │  ├─ pykotor.extract.Installation          http://:8080/mcp/           │
 │  ├─ chitin.key / BIF archives             → Ghidra repo :13100        │
 │  ├─ override/, modules/                      swkotor.exe / swkotor2   │
 │  └─ dialog.tlk                                                        │
 └────────────────────────────────────────────────────────────────────────┘
```

---

## 6. Compliance Audit: GhostRigger vs. Design Philosophy

### 6.1 Constantine Coupling Violations

| Violation | Location | Severity | Fix |
|---|---|---|---|
| `state.py` diverged from upstream | `src/kotormcp/state.py` | HIGH | Sync to upstream pattern; wrap with Ports for testability |
| `_load_gff_bytes` duplicated in `gamedata.py` + `gffdata.py` | Both files | MED | Extract to `adapters.py` |
| `asyncio.get_event_loop()` instead of `asyncio.run()` | test files | LOW | Fixed in v3.3 |
| Sync/async boundary: `asyncio.run()` inside Flask routes | `ipc/server.py` | MED | Document limitation; migrate to FastAPI when possible |
| `src/core/` imports in `ghostrigger.py` tools | Tool handler imports | LOW | Acceptable — tools are same process |

### 6.2 Tool Naming Violations

| Current Name | Convention Violation | Proposed Name |
|---|---|---|
| `detectInstallations` | camelCase, no verb clarity | `detect_installs` |
| `loadInstallation` | camelCase | `load_install` |
| `kotor_installation_info` | noun-heavy, redundant prefix | `get_install_info` |
| `listResources` | camelCase | `list_resources` |
| `describeResource` | camelCase | `describe_resource` |
| `ghostrigger_open_model` | app-prefixed | `open_model` |
| `ghostrigger_render_model` | app-prefixed | `render_model` |
| `ghostrigger_audit` | app-prefixed | `audit_model` |
| `journalOverview` | camelCase | `get_journal` |

**NOTE**: Renaming tools is a **breaking change** for all configured Claude Desktop / Cursor clients. The renaming should happen in a planned v4.0 migration with aliasing support (old name → new name redirect in `handle_tool`).

### 6.3 Cohesion Violations

| Module | Current Cohesion | Issue | Fix |
|---|---|---|---|
| `gamedata.py` | Logical | journalOverview + lookup_2da + lookup_tlk are three unrelated ops | Split: `journal.py` + keep lookup in `gffdata.py` |
| `gffdata.py` | Sequential | Deep reads (gff/2da/tlk) overlap with `gamedata.py` lookups | Merge gamedata lookups into gffdata; eliminate duplication |
| `tools/__init__.py` | Logical | Registry + dispatcher in one file | Acceptable at integration layer (Constantine §11) |

### 6.4 What Is Correctly Designed ✅

- **Ports & Adapters** (`ports.py` / `adapters.py`) — correct application of Khononov contract coupling
- **Tool registry fan-in** — all tools enter via one `handle_tool` dispatcher (high fan-in, no duplication)
- **AgentDecompile bridge** (`adapters_decompile.py`) — HTTP transport isolated from handlers correctly
- **Offline-first tests** — MockClient pattern, no real install required for any unit test
- **`get_resource` open/closed design** — decoder dispatch table, adding a format = one function

---

## 7. Missing Tools — Porting Plan from Upstream KotorMCP

The following 8 tools exist in upstream `KotorMCP` and must be added to GhostRigger's `kotormcp`:

### Tier A — High value, port immediately

**`refs.py`** (6 tools from upstream `refs.py`):
- `kotor_list_references` — list outbound refs from any resource
- `kotor_find_referrers` — find what references a script/tag/resref
- `kotor_find_strref_referrers` — find TLK strref usages
- `kotor_describe_dlg` — DLG structure summary
- `kotor_describe_jrl` — JRL quest summary (supersedes `journalOverview`)
- `kotor_describe_resource_refs` — all refs from one resource

These complement `get_quest` perfectly — `get_quest` builds context, `kotor_find_referrers` traces usage.

**`walkmesh.py`** (1 tool):
- `kotor_walkmesh_validation_diagram` — text diagram for LLM context about area layout

### Tier B — Port when write-back is ready

**`archives.py`** (2 tools):
- `kotor_list_archive` — list ERF/RIM/MOD/KEY contents
- `kotor_extract_resource` — write resource to disk (first write-back tool)

---

## 8. IPC Port Registry (canonical)

| Port | Tool | Server Type | Calls Out To |
|---|---|---|---|
| **7001** | GhostRigger | Flask HTTP (IPC) + MCP | :7003 (blueprint_saved) |
| **7002** | GhostScripter | Flask HTTP (IPC) | :7001 (open_mdl) |
| **7003** | GModular | Flask HTTP (IPC callback) | :7001 (open_mdl), :7002 (open_dlg) |
| **6400** | GhostScripter MCP | HTTP MCP | — |
| **7004** | GModular MCP | **PLANNED** | — |
| **8080** | AgentDecompile | External HTTP MCP | Ghidra :13100 |

---

## 9. HolocronToolset NCS Decompiler: Integration Path

The NCS decompiler in `HolocronToolset/src/toolset/utils/script_decompiler.py` requires:
- PyQt5 GUI (for file dialog prompts)
- A configured `ncsDecompilerPath` setting
- Windows `.exe` (platform limitation noted in code)

**Non-GUI path for MCP use**: Use `pykotor.resource.formats.ncs.compilers.ExternalNCSCompiler` directly, which is the underlying engine. This is already in the `Libraries/PyKotor` package.

```python
# Headless NCS decompile path (no Qt required):
from pykotor.resource.formats.ncs.compilers import ExternalNCSCompiler, KnownExternalCompilers
compiler = ExternalNCSCompiler(ncs_decompiler_path)
nss_text = compiler.decompile(ncs_bytes, tsl=False)
```

This should replace the `_decode_ncs` stub in `resource.py` and the NCS hint in `get_quest`.

---

## 10. Roadmap (Priority Order)

### Completed in v3.4 ✅

1. ✅ **Ported `refs.py` from upstream KotorMCP** → 6 new tools (43 total)
2. ✅ **Ported `walkmesh.py` from upstream KotorMCP** → 1 new tool
3. ✅ **Ported `archives.py` from upstream KotorMCP** → `kotor_list_archive`, `kotor_extract_resource`
4. ✅ **Fixed `utils/formatting.py` circular import** — implementation in `formatting.py`, `__init__.py` re-exports
5. ✅ **204 tests passing** across 5 test files (0 failures)

### Completed in v3.4.1 ✅ (PyKotor test suite review)

Targeted improvements derived from reviewing `PyKotor/Libraries/PyKotor/tests/` — specifically
`test_bwm.py`, `test_finder.py`, and `tests/cli/test_walkmesh_rebuild.py`.  No wholesale
integration; only surgically applied fixes where PyKotor tests revealed defects in our ports:

1. ✅ **walkmesh.py — raw bytes to `read_bwm()`**: PyKotor's `read_bwm(source)` signature accepts
   bytes directly; we were wrapping in `BytesIO` unnecessarily.  Removed the wrapper.
2. ✅ **walkmesh.py — `.bwm` suffix stripping**: resref sanitisation now strips both `.wok` **and**
   `.bwm` suffixes (PyKotor test_bwm.py validates both extensions).
3. ✅ **walkmesh.py — stats header**: Prepends `# stats: N faces, M walkable, P perimeter edges`
   to the diagram — PyKotor tests exercise `walkable_faces()` and `edges()`, so we expose them.
4. ✅ **refs.py — JSON-safe error serialisation**: All error paths now use `_err(msg)` which calls
   `json.dumps({"error": msg})`.  Previous f-string patterns like `'{"error": "{e}"}'` could
   produce invalid JSON when exception messages contained `"` or `\` characters.
5. ✅ **refs.py — `case_sensitive` parameter on `kotor_find_referrers`**: PyKotor's
   `find_referrers()` signature exposes `case_sensitive`; our schema now propagates it.
   Added to `FindReferrersInput` Pydantic model and JSON schema.
6. ✅ **refs.py — `restype.name` not `.extension`** for `extract_references` `file_type` arg:
   Avoids mismatch when `ResourceType.extension` and `.name` differ (e.g. `TWO_DA` → `"2da"` vs
   `"TWO_DA"`).  Using `.name.upper()` is consistent with how PyKotor callers pass file_type.
7. ✅ **16 new tests** in `TestWalkmeshToolModule`, `TestV341Improvements` — 160 total passing.

### Immediate (v3.5)

### Short term (v3.5)
5. **NCS decompiler integration** — headless `ExternalNCSCompiler` in `get_quest` + `get_resource`
6. **GModular MCP server** — add `Tools/GModular/gmodular/mcp/` package

### Medium term (v4.0)
8. **Tool name migration** — `verb_noun`, no prefix, with backward-compat aliases
9. **HolocronToolset merge** — GModular becomes the new HolocronToolset base
10. **Single `kotormcp` package** — upstream base + GhostRigger extension module

---

## 11. File Manifest (v3.4 additions)

```
GhostRigger-K1-K2/src/kotormcp/tools/
├── __init__.py       ← registry (v3.4: 43 tools)
├── refs.py           ← NEW v3.4: ported from upstream KotorMCP refs.py (6 tools)
├── walkmesh.py       ← NEW v3.4: ported from upstream KotorMCP walkmesh.py (1 tool)
├── archives.py       ← NEW v3.4: ported from upstream KotorMCP archives.py (2 tools)
├── resource.py       ← v3.3: get_resource
├── quest.py          ← v3.3: get_quest
├── installation.py   ← unchanged (3 tools)
├── discovery.py      ← unchanged (4 tools)
├── gamedata.py       ← unchanged (3 tools)
├── ghostrigger.py    ← unchanged (5 tools)
├── modules.py        ← unchanged (3 tools)
├── gffdata.py        ← unchanged (3 tools)
└── decompile.py      ← unchanged (11 tools)
```

---

## 12. References

| Document | Location |
|---|---|
| Constantine, *Structured Design* (1979) | `/home/user/uploaded_files/_OceanofPDF.com_Structured_design_-_Larry_L_Constantine.pdf` |
| Khononov, *Balancing Coupling* (2024) | `/home/user/uploaded_files/Balancing_Coupling_in_Software_Design_-_Vlad_Khononov.pdf` |
| Upstream KotorMCP | `Tools/KotorMCP/src/kotormcp/` |
| HolocronToolset | `Tools/HolocronToolset/src/toolset/` |
| GhostScripter MCP | `Tools/GhostScripter-K1-K2/ghostscripter/mcp/` |
| GModular IPC | `Tools/GModular/gmodular/ipc/` |
| GhostRigger KotorMCP | `src/kotormcp/` (this repo) |
| AgentDecompile | `src/kotormcp/adapters_decompile.py` + `AGENTDECOMPILE_INTEGRATION.md` |
| IPC Blueprint | `Tools/GModular/PIPELINE_SPEC.md` |
