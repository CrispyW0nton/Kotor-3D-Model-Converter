# GFF Diff Semantics and Reva Engine Research

## GFF Diff Output (Canonical, Industry-Standard)

The diff tool produces **canonical output** that clearly distinguishes:

| Category | Meaning | Example |
|----------|---------|---------|
| **MODIFIED** | Same logical entry, different fields (field-level diff shown) | Creature ResRef match, GuaranteedCount added |
| **ADDED** | Entry present only in new file | New creature in CreatureList |
| **REMOVED** | Entry present only in old file | Creature removed |
| **REORDERED** | Same entry, different index, no field changes | List reorder |
| **Summary** | `X modified, Y added, Z removed, W reordered` | Per-list totals |

When the **only** differences are ignorable (e.g., optional K2 field with default value, string whitespace/CRLF), the files report **MATCHES** with no spurious output.

## GFF List Semantic Identity Matching

When comparing GFF lists, the diff tool uses **semantic identity** for known list types to avoid false "added + removed" reports. For example, UTE `CreatureList` entries with the same creature (ResRef, CR, Appearance, SingleSpawn) but different optional fields (e.g., GuaranteedCount in K2) are matched by identity; if the only diff is ignorable, they are treated as **identical**.

### Registry: `_GFF_LIST_SEMANTIC_REGISTRY`

Located in `gff_data.py`. Maps `(GFFContent, list_field_name)` → `GFFListSemanticConfig`:

| GFF Type | List Field   | Identity Fields                         | Default When Absent   | Ignorable When Value |
|----------|--------------|-----------------------------------------|------------------------|----------------------|
| UTE      | CreatureList | ResRef, CR, SingleSpawn                 | GuaranteedCount: 0, Appearance: 0 | GuaranteedCount: 0   |

### Registry: `_GFF_IGNORABLE_FIELD_VALUES`

Maps `GFFContent` → `{field_name: {value1, value2, ...}}`. Fields added/removed with these values are not reported (engine default when absent).

| GFF Type | Field            | Ignorable Values | Engine Note                    |
|----------|------------------|------------------|--------------------------------|
| UTE      | GuaranteedCount  | {0}              | K2-only; engine reads 0 when absent |

### Adding New Semantic Configs

```python
_GFF_LIST_SEMANTIC_REGISTRY[(GFFContent.UTC, "ItemList")] = GFFListSemanticConfig(
    identity_fields=("InventoryRes", "ItemStackSize"),
    default_when_absent={"Repos_Pos": 0},
    ignorable_when_value={"Repos_Pos": 0},
)
```

### Adding Ignorable Fields

```python
_GFF_IGNORABLE_FIELD_VALUES[GFFContent.UTE]["GuaranteedCount"] = {0}
```

## String Normalization

GFF string fields are normalized before comparison to avoid false positives from:

- CRLF vs LF line endings
- Trailing whitespace per line and overall

See `_normalize_string_for_compare()` in `gff_data.py`.

## Reva Engine Research (Ghidra)

To verify construct/dismantle correctness and document engine behavior for each field in `Libraries/PyKotor/src/pykotor/resource/generics/`, the **Reva MCP server** must have both executables loaded in a Ghidra project:

1. **swkotor.exe** (KotOR I)
2. **swkotor2.exe** (KotOR II / TSL)

### Requirements

- Open project: `C:\Users\boden\PyKotorGhidraProject.gpr` (or equivalent)
- Import both `swkotor.exe` and `swkotor2.exe`
- Run auto-analysis
- Connect the Reva MCP server to this project

### Research Tasks (when Reva is available)

For **each** generic format (UTE, UTC, UTI, UTD, UTM, UTP, UTS, UTT, UTW, etc.):

1. Use `list-functions` / `get-functions` to find load/read/parse functions
2. Decompile and inspect how each field is read and what defaults apply
3. Document findings in `construct_<format>` / `dismantle_<format>` as inline comments
4. Verify field types and defaults for **both** K1 and TSL

### Known Engine References (from prior research)

- **UTE**: `CSWSEncounter::LoadEncounter` (K1: 0x00593830, TSL: TODO), `ReadEncounterFromGff` (K1: 0x00592430, TSL: TODO)
- **UTE CreatureList**: ResRef, CR, SingleSpawn, Appearance; GuaranteedCount is K2-only, default 0

## Default and Ignorable Fields

When `ignore_default_changes=True` (default for GFF diff):

- Fields added with default values (0, empty, -1, or values in `_GFF_IGNORABLE_FIELD_VALUES`) are not reported
- String fields are normalized (CRLF, trailing whitespace) before comparison
- Semantic config `default_when_absent` is used for **identity matching** so same-identity entries are correctly paired
