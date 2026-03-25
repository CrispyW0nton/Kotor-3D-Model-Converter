# AgentDecompile Integration — KotOR Odyssey Engine Reverse Engineering

This document describes how GhostRigger integrates with
[AgentDecompile](https://github.com/bolabaden/AgentDecompile) — an AI-powered
Ghidra MCP backend — and lays out a plan for how the combined toolset can be
used to research, document, and improve the KotOR modding pipeline.

---

## Overview

AgentDecompile exposes Ghidra's full reverse-engineering capability as MCP
tools. A shared server at `http://170.9.241.140:8080/mcp/` hosts
**fully-analysed KotOR Odyssey Engine binaries**:

| Binary | Ghidra path | Description |
|---|---|---|
| `swkotor.exe` (K1 GoG) | `/K1/k1_win_gog_swkotor.exe` | KotOR 1 Windows executable, ~24 000 functions |
| `swkotor2.exe` (K2/TSL) | `/K2/swkotor2.exe` | KotOR 2 / The Sith Lords executable |

No local Ghidra install is needed. All analysis runs on the remote server.

---

## MCP Server Configuration

Two MCP servers are registered in `claude_desktop_config.json`:

### 1. `ghostrigger-kotor` (GhostRigger + AgentDecompile bridge)

Runs the embedded KotorMCP server. Exposes **32 tools** covering:
- Installation discovery and resource browsing
- Model parsing, rendering, and auditing
- GFF/2DA/TLK data access
- Module analysis
- **11 AgentDecompile bridge tools** (via `src/kotormcp/tools/decompile.py`)

```json
{
  "command": "python",
  "args": ["-m", "src.kotormcp"],
  "cwd": "/path/to/GhostRigger-K1-K2",
  "env": {
    "K1_PATH": "/path/to/swkotor",
    "K2_PATH": "/path/to/swkotor2",
    "AGENTDECOMPILE_MCP_SERVER_URL": "http://170.9.241.140:8080/mcp/",
    "AGENTDECOMPILE_HTTP_GHIDRA_SERVER_HOST": "170.9.241.140",
    "AGENTDECOMPILE_HTTP_GHIDRA_SERVER_PORT": "13100",
    "AGENTDECOMPILE_HTTP_GHIDRA_SERVER_REPOSITORY": "Odyssey",
    "AGENTDECOMPILE_GHIDRA_USERNAME": "OpenKotOR",
    "AGENTDECOMPILE_GHIDRA_PASSWORD": "idekanymore"
  }
}
```

### 2. `agdec-proxy` (Native AgentDecompile stdio proxy)

Runs `agentdecompile-proxy` via `uvx` (no install needed). Exposes all
**39 native AgentDecompile tools** directly. Requires `uv` to be installed.

```json
{
  "type": "stdio",
  "command": "uvx",
  "args": [
    "--refresh",
    "--from",
    "git+https://github.com/bolabaden/AgentDecompile",
    "agentdecompile-proxy",
    "--mcp-server-url",
    "http://170.9.241.140:8080/mcp/"
  ],
  "env": {
    "AGENTDECOMPILE_PROJECT_PATH": "/projects/agentdecompile_projects/",
    "AGENTDECOMPILE_PROJECT_NAME": "Odyssey.gpr",
    "AGENTDECOMPILE_HTTP_GHIDRA_SERVER_HOST": "170.9.241.140",
    "AGENTDECOMPILE_HTTP_GHIDRA_SERVER_PORT": "13100",
    "AGENTDECOMPILE_HTTP_GHIDRA_SERVER_REPOSITORY": "Odyssey",
    "AGENTDECOMPILE_GHIDRA_USERNAME": "OpenKotOR",
    "AGENTDECOMPILE_GHIDRA_PASSWORD": "idekanymore"
  }
}
```

When both servers are active, Claude has simultaneous access to the full
GhostRigger asset pipeline AND the complete Ghidra analysis environment.

---

## Tool Inventory

### GhostRigger AgentDecompile Bridge Tools (`kotor_binary_*` / `kotor_*`)

These tools are implemented in `src/kotormcp/tools/decompile.py` and forward
to the AgentDecompile backend via `AgentDecompileClient` in
`src/kotormcp/adapters_decompile.py`.

| Tool | Use case |
|---|---|
| `kotor_binary_ping` | Verify backend connectivity before any analysis |
| `kotor_binary_info` | Confirm a binary is loaded; get language/compiler/function count |
| `kotor_list_engine_funcs` | Page through the 24 000+ function table |
| `kotor_decompile_function` | Get C pseudocode for any engine function |
| `kotor_search_symbols` | Find functions/globals matching a name pattern |
| `kotor_search_engine_strings` | Find hardcoded strings (file paths, format strings, errors) |
| `kotor_get_references` | Find all callers or callees of a function |
| `kotor_call_graph` | Map the call graph around a function (configurable depth) |
| `kotor_data_flow` | Trace P-code data flow backward or forward from an address |
| `kotor_inspect_memory` | View memory layout, raw bytes, or typed data at an address |
| `kotor_engine_script` | Run arbitrary Python/PyGhidra against the binary (full API) |

### Native AgentDecompile Tools (via `agdec-proxy`)

Available directly when the `agdec-proxy` server is running:

`analyze-data-flow`, `analyze-program`, `analyze-vtables`, `apply-data-type`,
`change-processor`, `checkin-program`, `checkout-program`, `checkout-status`,
`create-label`, `decompile-function`, `export`, `get-call-graph`,
`get-current-program`, `get-data`, `get-function`, `get-references`,
`import-binary`, `inspect-memory`, `list-cross-references`, `list-exports`,
`list-functions`, `list-imports`, `list-project-files`, `list-processors`,
`list-strings`, `manage-function-tags`, `match-function`, `migrate-metadata`,
`execute-script`, `open-project`, `read-bytes`, `search-code`,
`search-constants`, `search-everything`, `search-strings`, `search-symbols`,
`svr-admin`, `sync-project`, `remove-program-binary`

---

## Utilisation Plan

Below are planned research workflows that combine GhostRigger's asset pipeline
with AgentDecompile's engine analysis capability.

---

### Workflow 1 — MDL Binary Format Archaeology

**Goal:** Produce a complete, verified specification of the KotOR MDL/MDX binary
format by cross-referencing GhostRigger's parser with the engine's own loader code.

**Steps:**

1. **Find the MDL loader in the binary**
   ```
   kotor_search_symbols  game=k1  query=MDL
   # → CResMan::LoadResourceMDL, CMDLObject::Load, CMDLMesh::Read, ...
   ```

2. **Decompile the top-level loader**
   ```
   kotor_decompile_function  game=k1  function=CMDLObject::Load
   ```
   Cross-reference header offsets, node type IDs, and flag values with
   `src/core/mdl_parser.py`.

3. **Decompile mesh and skin node parsers**
   ```
   kotor_decompile_function  game=k1  function=CMDLMesh::Read
   kotor_decompile_function  game=k1  function=CMDLSkin::ReadWeights
   ```

4. **Verify MDX bitmap flag values**
   ```
   kotor_search_engine_strings  game=k1  pattern=MDX
   kotor_inspect_memory  game=k1  address=<flag_table_address>  mode=defined
   ```

5. **Document any undocumented node types** discovered in the decompiled output
   and add them to `src/core/mdl_parser.py`.

---

### Workflow 2 — Resource Manager Architecture Map

**Goal:** Understand how the Odyssey Engine's resource manager (`CResMan`) loads
KEY/BIF/ERF/RIM archives so GhostRigger's `game_library_ext.py` can be verified
and hardened.

**Steps:**

1. **Map the CResMan class hierarchy**
   ```
   kotor_search_symbols   game=k1  query=CResMan
   kotor_call_graph       game=k1  function=CResMan::Startup  depth=3
   ```

2. **Decompile the BIF reader**
   ```
   kotor_decompile_function  game=k1  function=CResMan::LoadBIF
   ```
   Verify key file header offsets used in `game_library_ext.py`.

3. **Trace ERF override priority logic**
   ```
   kotor_decompile_function   game=k1  function=CResMan::GetResource
   kotor_get_references       game=k1  address_or_symbol=CResMan::GetResource  direction=to
   ```

4. **Find hardcoded resource type extension table**
   ```
   kotor_search_engine_strings  game=k1  pattern=.tpc
   kotor_search_engine_strings  game=k1  pattern=.utc
   ```

---

### Workflow 3 — Save-Game Format Reverse Engineering

**Goal:** Document KotOR's save-game (`.sav`) serialisation format for potential
future GFF/save editor support.

**Steps:**

1. **Find the save-game serialiser**
   ```
   kotor_search_symbols         game=k1  query=Save
   kotor_search_engine_strings  game=k1  pattern=.sav
   ```

2. **Decompile save/load entry points**
   ```
   kotor_decompile_function  game=k1  function=CGameState::Save
   kotor_decompile_function  game=k1  function=CGameState::Load
   ```

3. **Trace data flow through serialisation**
   ```
   kotor_data_flow  game=k1  function_address=<CGameState::Save addr>  direction=forward
   ```

---

### Workflow 4 — Animation System Analysis

**Goal:** Understand the keyframe interpolation and SLERP implementation in the
engine to validate and improve `src/core/animation_engine.py`.

**Steps:**

1. **Find animation playback functions**
   ```
   kotor_search_symbols  game=k1  query=Anim
   kotor_search_symbols  game=k1  query=SLERP
   ```

2. **Decompile the interpolator**
   ```
   kotor_decompile_function  game=k1  function=CAnimController::Interpolate
   ```

3. **Compare quaternion arithmetic** with `animation_engine.py` slerp
   implementation; correct any numerical differences.

---

### Workflow 5 — NWScript VM Bytecode Format

**Goal:** Document the NWScript `.ncs` bytecode instruction set so GhostRigger
can eventually add script disassembly support.

**Steps:**

1. **Find the script VM**
   ```
   kotor_search_symbols         game=k1  query=CScriptVM
   kotor_search_engine_strings  game=k1  pattern=NCS
   ```

2. **Decompile the opcode dispatch loop**
   ```
   kotor_decompile_function  game=k1  function=CScriptVM::Execute
   ```

3. **Extract opcode table** using a PyGhidra script:
   ```python
   # kotor_engine_script  game=k1
   vm_fn = getFunction("CScriptVM::Execute")
   # walk the switch table and emit opcode → handler name map
   for ref in vm_fn.getBody():
       ...
   ```

---

### Workflow 6 — K1 vs K2 Binary Diff

**Goal:** Identify structural differences between `swkotor.exe` and `swkotor2.exe`
that explain K1↔K2 MDL format incompatibilities.

**Steps:**

1. **Compare function lists**
   ```
   kotor_list_engine_funcs  game=k1  limit=500
   kotor_list_engine_funcs  game=k2  limit=500
   # Compare MDL-related function names between the two binaries
   ```

2. **Decompile the same function in both games**
   ```
   kotor_decompile_function  game=k1  function=CMDLObject::Load
   kotor_decompile_function  game=k2  function=CMDLObject::Load
   # Diff the pseudocode to find format version checks and struct size changes
   ```

3. **Document discovered differences** in `src/core/mdl_porter.py` comments
   and update the `CrossGamePorter` patch table accordingly.

---

## Architecture Notes

### Why two servers?

- **`ghostrigger-kotor`** provides the _integrated_ experience: the 11
  `kotor_binary_*` tools are purpose-built for KotOR modding, with `k1`/`k2`
  aliases, KotOR-specific descriptions, and clean JSON responses that pair
  well with the other 21 GhostRigger tools.

- **`agdec-proxy`** provides the _full_ AgentDecompile tool set (39 tools)
  for tasks that need lower-level Ghidra access: `apply-data-type`,
  `create-label`, `export`, `migrate-metadata`, `svr-admin`, etc.

Both can be active simultaneously. Claude will naturally pick the right server
for each task.

### Credential Note

The Ghidra shared-server RMI port (13100) currently rejects the `OpenKotOR`
credentials during `open-project` calls (FailedLoginException). The HTTP MCP
server on port 8080 is healthy and responds to all `kotor_binary_*` tool calls.
The `agdec-proxy` likewise operates against the HTTP endpoint and works
correctly. Until the Ghidra RMI credentials are updated, `checkout-program`
and other shared-repo tools are not available; all other tools function normally.

### Environment Variable Precedence

`adapters_decompile.py` checks both prefix forms in order:

```
AGENTDECOMPILE_MCP_SERVER_URL  →  AGENT_DECOMPILE_MCP_SERVER_URL
AGENTDECOMPILE_HTTP_GHIDRA_SERVER_HOST  →  AGENT_DECOMPILE_GHIDRA_SERVER_HOST
AGENTDECOMPILE_HTTP_GHIDRA_SERVER_PORT  →  AGENT_DECOMPILE_GHIDRA_SERVER_PORT
AGENTDECOMPILE_HTTP_GHIDRA_SERVER_REPOSITORY  →  AGENT_DECOMPILE_GHIDRA_SERVER_REPOSITORY
AGENTDECOMPILE_GHIDRA_USERNAME  (new prefix only)
AGENTDECOMPILE_GHIDRA_PASSWORD  (new prefix only)
```

---

## Testing

All 53 bridge tests in `tests/test_agentdecompile_bridge.py` are **fully offline**
(no network calls). The real `AgentDecompileClient` is replaced by `MockClient`
in every handler test, and all HTTP calls in `_post()` / `_initialize()` are
never invoked.

Test coverage:
- `AgentDecompileClient` unit tests (constructor, URL normalisation, path
  resolution, header generation, session ID management, singleton lifecycle)
- Tool schema validation (all 11 tools: name, description, inputSchema, required fields)
- Tool handler logic (input validation, error propagation, client delegation,
  response field presence)
- Registry integration (all decompile tools present in `get_all_tools()`,
  total count == 32, all 11 dispatch paths exercised, unknown-tool raises `ValueError`)

Run:
```bash
pytest tests/test_agentdecompile_bridge.py -v
# 53 passed in ~0.4 s
```
