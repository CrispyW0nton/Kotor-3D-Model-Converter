# Python Engineering Skill

Use this skill for Python implementation quality, modules/packages, iterators,
files/IO, data processing, testing/debugging, C extensions, and embedded Python
payload care.

## Book Grounding

- `Python_Cookbook_-_David_Beazley_Brian_K_Jones.pdf`: data structures,
  iterators/generators, files/IO, encoding/processing, functions, classes,
  metaprogramming, modules/packages, concurrency, utility scripting,
  testing/debugging/exceptions, and C extensions.
- `Pro_Python_Experts_Voice_in_Open_Source_1st_Edition_-_Marty_Alchin.pdf`:
  Python principles, explicitness, loose coupling, robust errors, iteration,
  caching, control flow, collections, and import behavior.
- `Dive_Into_Python_3_-_Mark_Pilgrim.pdf`: Python 3 syntax, native data types,
  comprehensions, files/directories, strings, regex, closures, classes,
  iterators, unit testing, serialization, and packaging.
- `Python_for_Dummies_-_Aahz_Maruch.pdf`: basic language and standard-library
  reference; use mainly for quick beginner-level refreshers.

## Workflow

1. Prefer simple, explicit Python that fits the owning subsystem style.
2. Use iterators/generators for streaming data, not for obscuring small simple
   transformations.
3. Use `pathlib`, context managers, and structured parsers/serializers for file
   work.
4. Keep imports directional and local only when they intentionally avoid optional
   dependency cost or circular import at a boundary.
5. Make errors visible and domain-specific. Do not silently swallow exceptions
   unless the fallback is explicit and tested.
6. Use dataclasses/value objects for structured domain records where the repo
   already follows that style.
7. Use small helper functions when they name a real concept; avoid dumping
   miscellaneous code into broad utility modules.
8. For concurrency, state thread/process ownership and UI-thread handoff rules.

## GhostRigger Applications

- Canonical source edits under `src/`.
- Embedded Python payload regeneration for native packages.
- Headless core/service tests.
- Resource parsers, validation reports, KMAX/KMAP serialization, and renderer
  descriptors.
- Python terminal cheatsheet helpers.

## Validation

- Run `python -m py_compile` on changed Python files.
- Prefer targeted pytest cases tied to the owning subsystem.
- If changed files are packaged into native DLLs, regenerate payloads and run
  focused native payload tests.
- For C-extension or ctypes boundaries, test error cases and type conversions.
