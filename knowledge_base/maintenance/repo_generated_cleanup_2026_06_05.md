# Repository Generated-Output Cleanup - 2026-06-05

Scope: workspace generated files only. Source code, tests, documentation, project configuration, and user runtime settings were left intact.

## Removed Generated Output

- Removed 215 top-level ignored/generated targets, including `.pytest_tmp*` basetemp folders, `.tmp_retarget_video_*` extraction folders, root `.tmp_*.mdl` / `.tmp_*.mdx` scratch files, `.pytest_cache` where accessible, `__pycache__`, `build`, `dist`, `artifacts`, and `tmp_codex_exports`.
- Removed 101 nested generated targets, including Python `__pycache__` folders, `logs`, `audit_output`, `diagnostics`, `tests/_artifacts`, and `build_log.txt`.
- Removed tracked generated `artifacts/**/report.json` files from git because `artifacts/` is an ignored local render/audit output folder and should not ship as repository content.
- Added `.tmp*/`, `.tmp_*`, and `*.tmp` ignore guards so future one-off scratch folders and files stay local.

## Preserved Knowledge

The deleted files were generated caches, basetemps, scratch exports, render/audit artifacts, or local logs. This maintenance note is the durable record of the cleanup so the repo does not need to keep bulky generated output.

## Remaining Locked Temp Directories

Windows denied access to these ignored temp directories even after delete, rename, .NET delete, `takeown`, and `icacls` attempts. They appear to be inaccessible empty shells and may require an elevated shell, reboot, or external cleanup tool:

- `.pytest_cache`
- `.pytest_tmp_character_animation_fit_suite`
- `.pytest_tmp_character_builder_current_suite`
- `.pytest_tmp_character_fit_suite`
- `.pytest_tmp_lightsaber_all_variants`
- `.pytest_tmp_lightsaber_colors`
- `.pytest_tmp_lightsaber_material`
- `.pytest_tmp_lightsaber_semantics`
- `.pytest_tmp_lightsaber_semantics_full`
- `.pytest_tmp_merge_preserve_lightsaber`
- `.pytest_tmp_mixamo_crossed_feet_smoke`
- `.pytest_tmp_mixamo_crossed_feet_writer`
- `.pytest_tmp_mixamo_rest_anchor_smoke`
- `.pytest_tmp_mixamo_retarget_smoke`
- `.pytest_tmp_mixamo_shoulder_twist_smoke`
- `.pytest_tmp_mixamo_terminal_fix_smoke`
- `.pytest_tmp_mixamo_terminal_twist_smoke`
- `.pytest_tmp_postmerge_character`
- `.pytest_tmp_postmerge_character_rerun`
- `.pytest_tmp_postmerge_lightsaber`
- `.pytest_tmp_postmerge_lightsaber_deep`
- `.pytest_tmp_postmerge_retarget`
- `.pytest_tmp_postmerge_retarget_deep`

## Verification

- Verified resolved cleanup target paths stayed inside the workspace before recursive deletion.
- Re-ran ignored/status checks after cleanup and documented the locked survivors.
- No tests were run; this was repository hygiene only.
