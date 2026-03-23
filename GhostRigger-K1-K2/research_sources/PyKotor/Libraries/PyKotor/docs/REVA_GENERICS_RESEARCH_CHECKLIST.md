# REVA Engine Research Checklist for GFF Generics

This document tracks reverse engineering research for construct/dismantle correctness across **both** `swkotor.exe` (K1) and `swkotor2.exe` (TSL).

## Prerequisites

1. **Open Ghidra project** via REVA MCP:
   ```
   open path="C:\Users\boden\PyKotorGhidraProject.gpr"
   ```
2. Ensure both executables are imported and analyzed.
3. Research **both** games for each field; document K1 and TSL addresses/behavior.

## Format-by-Format Checklist

### UTE (Encounter)

| Field | Path | Type | Default | K1 Addr | TSL Addr | Notes |
|-------|------|------|---------|---------|----------|-------|
| Appearance | CreatureList/N | Int32 | 0 | TODO | TODO | |
| CR | CreatureList/N | Float | 0.0 | TODO | TODO | |
| SingleSpawn | CreatureList/N | UInt8 | 0 | TODO | TODO | |
| ResRef | CreatureList/N | ResRef | blank | TODO | TODO | |
| GuaranteedCount | CreatureList/N | Int32 | 0 | N/A (K2 only) | TODO | |

### UTC (Creature), UTI (Item), UTD (Door), UTM (Store), UTP (Placeable), UTS (Sound), UTT (Trigger), UTW (Waypoint)

See `Libraries/PyKotor/src/pykotor/resource/generics/` for each module. Add inline comments in construct_/dismantle_ functions with:

- Engine function name and address (K1, TSL)
- Field type and default when absent
- Any 0xFFFFFFFF or -1 sentinel semantics

## Research Protocol

For each field:

1. Search for GFF label string (e.g. `"GuaranteedCount"`) in both executables.
2. Trace to load/parse function; decompile.
3. Document: type read, default when absent, any special handling.
4. Add comment in construct_/dismantle_ at the field line.

## Address Format

Use: `FunctionName @ (K1: 0xADDRESS, TSL: 0xADDRESS)` or `TODO` if unknown.
