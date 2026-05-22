# Odyssey Ghidra MCP Workflow

Purpose: use the AgentDecompile/Ghidra MCP bridge as engine ground truth when
GhostRigger behavior depends on `swkotor.exe` / `swkotor2.exe` binary semantics.

Do not commit server credentials or MCP passwords into the repository. Keep
connection secrets in the local MCP configuration only.

## Available Tool Surface

The GhostRigger MCP exposes these Ghidra-backed helpers:

- `kotor_binary_ping()` - verify the AgentDecompile backend and known programs.
- `kotor_binary_info(game="k1" | "k2")` - confirm the loaded executable.
- `kotor_search_symbols(game, query)` - find named functions/globals.
- `kotor_search_engine_strings(game, pattern)` - find string literals.
- `kotor_decompile_function(game, function)` - get decompiler output or
  disassembly when the decompiler process is unavailable.
- `kotor_get_references(game, address_or_symbol, direction)` - list callers or
  callees.
- `kotor_call_graph(game, function, depth)` - inspect subsystem call flow.
- `kotor_data_flow(game, function_address, start_address, direction)` - trace
  local value flow.
- `kotor_inspect_memory(game, address, mode, length)` - inspect raw memory,
  data, vtables, and static tables.

Use `game="k1"` for `/K1/k1_win_gog_swkotor.exe` and `game="k2"` for
`/K2/swkotor2.exe`.

## Export-Crash Pattern: MaxTree Subtype

K1 live testing exposed a crash in `InputBinary::Read` at `0x004A136D`. Ghidra
ground truth:

- `MaxTree::AsModel` at `0x0043E1C0` reads byte `[ECX + 0x4C]`.
- It masks that byte with `0x7F`.
- It returns `(Model *)this` only when the masked subtype equals `0x02`.
- `InputBinary::Read` then writes through `[EAX + 0xB4]`; if `AsModel` returned
  null, this becomes an access violation.

Writer implication:

- Top-level MDL geometry header must write `0x02` at geometry block `+0x4C`.
- Animation geometry blocks must write `0x05` at animation block `+0x4C`.
- These bytes are engine-facing MaxTree subtypes, not display metadata.

The regression test is `tests/test_roundtrip_verification.py::
test_mdl_writer_sets_engine_maxtree_subtype_bytes`.

## Model Header Size

PyKotor's `_ModelHeader.SIZE` is `0xC4` / 196 bytes. That size includes:

- `0x00..0x4F`: 80-byte geometry header;
- `0x50..0xC3`: 116 bytes of model fields.

The late model fields are engine-facing and must not be moved behind a custom
GhostRigger name-block header:

- `+0xA8` `offset_to_super_root` should point at the model root node offset;
- `+0xAC` `mdx_data_buffer_offset` is usually 0 for the emitted MDX buffer;
- `+0xB0` `mdx_size` must match the MDX byte length;
- `+0xB4` `mdx_offset` is usually 0 for the companion MDX;
- `+0xB8` `offset_to_name_offsets` points to the uint32 name-offset table;
- `+0xBC` and `+0xC0` are duplicate name-offset counts.

Stock `PMBAM` has `offset_to_name_offsets = 0xC4`, meaning the name-offset
table starts immediately after `_ModelHeader`. GhostRigger exports should keep
that canonical layout unless a specific source file requires preservation of a
different valid offset.

The regression test is `tests/test_roundtrip_verification.py::
test_mdl_writer_emits_full_engine_model_header_fields`.

## Recommended Use

Use Ghidra MCP when:

- a generated MDL crashes the game but GhostRigger/PyKotor can parse it;
- a writer offset or subtype byte is uncertain;
- live engine behavior differs from viewport/readback behavior;
- a K1/K2 binary behavior difference is suspected.

Record durable findings in `knowledge_base/` and add a focused regression test
near the writer/loader code that consumed the finding.
