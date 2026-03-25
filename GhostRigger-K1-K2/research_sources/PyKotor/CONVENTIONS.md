# Conventions

- Use types everywhere possible.
- Type hint local variables when it improves readability/safety (especially intermediate values in non-trivial functions).
- **Static type checking**: Adhere to static type checking principles. Do not use `getattr` or `hasattr`; use explicit typed attributes and `isinstance()` or protocol/type-narrowing instead. Reflective attribute access is not type-checker friendly and hides contract violations.
- **No defensive coding**: Do not add defensive guards (e.g. "if attribute exists then use it else create it") to paper over missing or inconsistent contracts. Fix the root cause: ensure base classes or call sites establish the correct invariants so that attributes and types are guaranteed at the point of use.
- **GFF / ResourceType**: Prefer `GFFContent` and `ResourceType` enums over raw strings when referring to file/content types. For ignorable-field registries, diff semantics, or per-type config, key by `(GFFContent, str | None)` where the str is the list field name (e.g. `"CreatureList"`) or `None` for root-level. Use `frozenset` for immutable value sets in registries. See `gff_data.py` `_GFF_IGNORABLE_FIELD_VALUES` and `_GFF_LIST_SEMANTIC_REGISTRY`.
- Give attributes types in __init__ immediately.
- Wrap each arg to a newline in a function if it has more than 2 args.
- Don't use title-case types from the typing module, this includes Optional and Union. Use `from __future__ import annotations` to allow type hints to be evaluated at runtime (e.g. `str | None`).
- Prefer fast-exit functions over nested conditionals.
- Inside loops, prefer negated guard + `continue` over wrapping the main body in a nested positive conditional when this reduces indentation.
- Consider how the program will continue if an exception is raised unexpectedly, and ensure that it does so gracefully.
- Avoid silent failures: if catching broad exceptions for UI resilience, log context at warning/debug level unless noise would be harmful.
- (if using qt in python) always import from qtpy.QtWidgets, qtpy.QtGui, and qtpy.QtCore etc.
- For repeated behavior across editors/windows (e.g., GIT editor, Module Designer, Indoor Builder), extract shared helpers/pipelines into `toolset.gui.common` instead of copying logic.
- Prefer small, composable helper functions for UI pipelines (populate widgets, scale preview images, toggle checkbox groups) and keep window classes orchestration-focused.
- Keep side-effect boundaries explicit: helper functions should either mutate UI state or compute values, not both unless clearly documented.

## Additional typing/performance conventions

- Do not use `dataclass` for performance-sensitive/editor data carriers in Toolset code; prefer `TypedDict`, explicit classes, or tuple/dict structures as appropriate.
- Do not use `Any` when a concrete type, `Protocol`, or callable signature can be expressed.
- For imports that can create cyclical dependencies, import inside a `TYPE_CHECKING` block (for type-only references) or inside the function scope (for runtime use).
- Define `TypedDict` class definitions inside a `TYPE_CHECKING` block.
