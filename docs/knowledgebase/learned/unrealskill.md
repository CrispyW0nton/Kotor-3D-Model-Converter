# Unreal And Technical Art Skill

Use this skill for Unreal-related workflow design, editor integration,
technical-art pipelines, Blueprints, world blockout, landscapes, materials, and
GhostRigger-to-Unreal handoff.

## Book Grounding

- `Extending_and_Customizing_Unreal_Engine_Editor_-_Roger_Mattsson.pdf`:
  plugins, `.uplugin`, `Build.cs`, editor modes, tools, undo/redo, user
  feedback, toolkits/widgets, toolbar actions, editor windows, tree views,
  sorting/filtering, context menus, data visualization, and custom Slate
  widgets.
- `Mastering_Technical_Art_in_Unreal_Engine_World_-_Greg_Penninck.pdf`: world
  building, references, project goals, actors/levels/experience, level
  streaming, world outliner conventions, blockout, landscape creation,
  heightmaps, landscape materials, material functions, and layered materials.
- `Unreal_Engine_Blueprint_Game_Developer_-_Asadullah_Alam.pdf`: present in the
  local library but not machine-readable via the current PDF extractor; inspect
  manually before deriving detailed Blueprint rules from it.

## Workflow

1. Define the handoff target: editor plugin, Blueprint workflow, asset export,
   level/world data, material setup, animation handoff, or validation report.
2. Keep editor tooling reversible. Undo/redo, selection preservation, clear user
   feedback, and non-destructive defaults matter more than clever automation.
3. Separate data model, editor UI, and runtime asset output.
4. For world/level tools, start with blockout, naming, outliner organization,
   streaming/level boundaries, and validation before polish.
5. For technical art, document source asset assumptions, material functions,
   texture inputs, generated assets, and what Unreal owns after import.
6. For Blueprint-facing features, expose clean, small operations with obvious
   names and predictable side effects.
7. Prefer staged export and proof artifacts over direct mutation of user
   projects.

## GhostRigger Applications

- Unreal Animator workbench.
- KMAX/KMAP export/handoff concepts.
- Technical-art validation reports.
- Material/texture pipeline naming and proof records.
- Future Unreal plugin or editor integration surfaces.

## Validation

- Validate staged files and manifests before any external editor/project write.
- Keep visible proof for user workflows.
- If integration reaches Unreal directly, document the editor version, plugin
  target, generated files, and rollback path.
