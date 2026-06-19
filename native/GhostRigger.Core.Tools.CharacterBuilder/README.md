# GhostRigger.Core.Tools.CharacterBuilder

Phase 1 native toolbox package boundary for Character Studio helpers.

- Owner surface: Character Studio.
- Owner package: `native/GhostRigger.Core.Tools.CharacterBuilder`.
- Bridge method: C ABI DLL.
- Data ownership: C++ owns diagnostic autofit packet metadata, native skinning
  validation metadata, and readback helper contracts. Python owns Character
  Studio UI, source asset selection, game semantics, save/export decisions, and
  MCP-backed validation.
- Verification: `GhostRigger.Core.Tools.CharacterBuilder` `Debug|x64` build, targeted Python
  package registry tests, backend truth checks before native helper output
  replaces Python behavior, and visible app checks only when UI/workflow
  behavior changes.

This package is diagnostic-only in Phase 1. It must not mutate character assets
or replace Python Character Studio workflow until parity gates are defined and
passed.
