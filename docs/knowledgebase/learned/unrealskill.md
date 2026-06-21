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

## Editor Tool Contract

- Every editor action should have undo/redo or a clear reason it is read-only.
- Tool settings should be inspectable and persisted through the editor's normal
  settings path when they affect repeated work.
- Long operations should expose progress and cancellation.
- List/tree views should support the columns, sorting, filtering, and context
  actions that make the data useful.
- Data visualization should be designed for someone returning months later, not
  only for the person who wrote the tool.
- Engine edits are last resort. If unavoidable, mark and isolate them so future
  merges can identify the modified region.

## Technical-Art Handoff Checklist

- Source references and goals are recorded.
- World/level/blockout ownership is clear.
- Generated assets have predictable names and folder placement.
- Materials identify required textures, material functions, layers, and
  parameter defaults.
- Landscape/heightmap workflows preserve dimensions, scale, and layer semantics.
- Staged exports include validation/proof files before any external project is
  modified.

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
