# GhostRigger Agent Instructions

## You have MCP tools. Use them.

Before writing or modifying any code that handles MDL loading, vertex transforms, 
textures, skinning, or rendering, FIRST query the MCP tools to get ground-truth data 
from the actual game files. Do not guess. Do not assume based on code comments.

## The GhostRigger GUI does NOT need to be running

The MCP tools in ghostrigger_tools.py import GhostRigger's Python modules directly.
The PYTHONPATH in .cursor/mcp.json includes the GhostRigger root directory.
If you get an ImportError, fix the import path — don't ask the user to open GhostRigger.

## When fixing a bug:
1. Use compare_model_pipelines(game, resref) to confirm the bug exists
2. Use inspect_mdl(game, resref) to get PyKotor ground truth
3. Use inspect_mdl_ghostrigger(game, resref) to see what GhostRigger produces
4. Identify the divergence
5. Fix the code
6. Re-run compare_model_pipelines to confirm the fix
7. Run the full scan on affected model category to check for regressions

## When running tests:
- `pytest tests/ -x` for quick validation
- `pytest tests/ -m "not slow"` to skip full-scan tests
- `pytest tests/test_mcp_full_scan.py` for the complete 6,078-model validation

## Commit format:
fix(scope): short description
feat(scope): short description  
chore(cleanup): short description
test(scope): short description
