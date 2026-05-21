# GhostRigger Stock KOTOR Test Corpus

This directory contains stock KOTOR MDL/MDX files extracted directly from the
BIF archives of a known-clean install. They exist so GhostRigger's retargeter
tests have a stable, reproducible baseline that is independent of:

- The user's live KOTOR install state
- The KOTOR Patch Manager's working state
- Any `Override/` content from other projects
- Any DLL-injection patcher state

## Rules

- DO NOT modify these files.
- DO NOT copy from `Override/` to refresh them. Re-extract from BIF.
- DO NOT depend on the live KOTOR install in any test. Point at this corpus.
- DO check the SHA256 of each file against `manifest.json` before any
  identity-round-trip test. If it does not match, fail loudly.

## Refresh

Regenerate the local corpus with:

```powershell
python scripts/extract_stock_corpus.py `
  --kotor-install "C:/Program Files (x86)/Steam/steamapps/common/swkotor" `
  --game k1 `
  --output tests/fixtures/kotor_stock/ `
  --k1-version "/K1/k1_win_gog_swkotor.exe via Ghidra Odyssey repo"
```

The extractor reads `chitin.key` / BIF-backed resources directly and bypasses
`Override/`.

## Out Of Scope

The live KOTOR `Override/` at
`C:\Program Files (x86)\Steam\steamapps\common\swkotor\Override` is owned by
other projects such as the Patch Manager. GhostRigger does not read, write, or
assume anything about its state for retargeter tests.

`custom_mixamo_a1` and similar artifacts in the live install are expected noise.
Tests must filter them out, not delete them.
