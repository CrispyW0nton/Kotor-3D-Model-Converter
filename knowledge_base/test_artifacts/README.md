# Test Artifact Archives

This folder stores archived local test-run leftovers that are worth keeping for
development history but should not live at the repository root.

Current cleanup rule:

- Root `.pytest_tmp*`, `.tmp*`, and `.pytest_cache` directories should be zipped
  here with a matching `.manifest.txt`, then removed from the workspace root.
- Keep generated runtime folders such as `artifacts/`, `logs/`, and `exports/`
  ignored unless a specific report or small reproduction is intentionally
  promoted into the knowledge base.
- Do not move production source, config, fixtures, or project architecture files
  into this folder.
