# Custom Rigged Character Builder architecture

Status: active implementation contract
Owner: LordVaderCW
Date: 2026-07-19

## Product boundary

The Character Builder entry point exposes two explicit products:

1. **Native KOTOR Character** opens the existing `QtCharacterBuilderWindow`.
   Its native KOTOR hierarchy, template rig, supermodel, skin transfer, and
   export behavior remain unchanged and independently testable.
2. **Custom Rigged Character** opens a separate guided workflow that converts
   a foreign FBX hierarchy into a self-contained Odyssey model. It does not
   rename the hierarchy to a stock humanoid rig and does not call
   `apply_template_rig()`.

The selected product mode is stored in its project document. A two-card welcome
selector is the default entry experience; an in-window `Character type` control
provides a compact route when reopening an existing project.

## Ownership and dependency direction

| Responsibility | Owner | Reuse or new work |
| --- | --- | --- |
| Versioned portable custom-character document, migrations, relative paths, source hashes, automatic save | `GhostRigger.Core.Project` | New `CustomRiggedCharacterProject` contract |
| Hierarchy, bind, skin, transform, ground, animation, registry, resource-name, material, and UV rules | `GhostRigger.Core.Validation` | New custom-rig validator; reports may publish through `ValidationBus` |
| Import-to-build orchestration, deterministic report assembly, repair audit, semantic animation mapping | `GhostRigger.Core.Workflow` | New controller/build service; reuse stable import and MDL/MDX services |
| FBX decoding, texture conversion, Odyssey serialization, UTC/2DA formats | `GhostRigger.Core.IO` and format/resource owners | Reuse stable low-level services; no custom UI policy in IO |
| Guided nine-step window, selector, nontechnical explanations, preview controls | `GhostRigger.Core.GUI.Display` | New UI module; thin calls into project/validation/workflow services |
| Merge-safe appearance/UTC/registry package and Patch Manager handoff | `GhostRigger.Core.Workflow` / KOTOR Patch Manager | New headless packaging/install transaction over existing IO formats and the external verified patch route |

Core and workflow modules remain Qt-free. The native builder does not gain
foreign-rig conditionals; it only exposes a navigation signal to the entry
controller. The custom UI must not subclass the native builder window.

## Guided workflow

The custom window owns these stable step IDs:

1. `source_assets` — project name, resref, target game, FBX, external clips,
   texture folder, output folder, hashes, recent paths, and import summary.
2. `rig_inspection` — mesh/skeleton/bind/floor preview and hierarchy, weights,
   transforms, unsupported controls, dimensions, origin, and facing checks.
3. `scale_ground` — global scale, facing, pivot, contact points, and ground
   offset with comparison silhouette.
4. `animation_library` — source clip inventory and confirmed vanilla aliases,
   custom registry actions, or unassigned clips.
5. `animation_preparation` — trim, loop, retime, sampling, root motion,
   continuity, contact, and explicit retargeting controls.
6. `materials_uvs` — material assignment, source/KOTOR/checker previews, UV
   wrapping, explicit DCC-to-KOTOR image-row orientation, alpha, TGA/TPC
   conversion, generated cutout TXI defaults, and advanced TXI overrides.
7. `gameplay` — installed UTC template catalog, behavior inheritance,
   appearance, UTC, collision, sound, per-event scripts, compiled custom hooks,
   optional compiled advanced spawn helper, verified temporary PLCaa placement,
   and missing-behavior warnings.
8. `validate_build` — full preflight, accepted warnings, deterministic MDL/MDX
   and package output, hashes, and persistent JSON/text evidence.
9. `install_test` — read-only exact file preview, game-closed install check,
   backup-safe Patch Manager handoff, restore route, and the beginner runtime
   checklist.

Implementation terms such as Aurora controllers, MDX streams, and supermodel
name tables stay in expandable Advanced sections and reports, not the welcome
screen.

## Conversion contract

The build service converts the selected foreign deform hierarchy into Odyssey
nodes while preserving valid names, parent/child relationships, bind pose,
weights, and local animation targets. Constraints, IK, control rigs, and
procedural motion must be baked or explicitly rejected. Every exported skin
influence and animation track must resolve to the same exported node set.

The selected single FBX authoring root is absorbed by the resource-named model
root. Its direct children are linked below `heightdummy -> cutscenedummy`, and
the same substitution is made in every animation block. For example, Borhek's
`godnode` becomes `c_borhek`; exporting both names creates a second root layer
that does not match the proven Odyssey creature tree. Reload validation rejects
that duplicate-root form. Position tracks whose entire delta is below `1e-5`
are omitted as FBX bake noise, while meaningful translations such as
`root_joint` motion are retained.

Blender mesh inspection remains loop-flattened for faithful split normal/UV
preview, but each loop records its original FBX control-point index. Palette
partitioning restores those indices before writing MDX skin rows. This makes
the Borhek output use the same 2,302 partition-local vertex rows and the same
231,700-byte MDX footprint as the working prototype rather than 9,174
triangle-corner rows.

Skeleton compatibility, animation-request compatibility, and gameplay
integration are separate validation groups. A valid skeleton does not imply
that attacks, deaths, hooks, sounds, or scripted actions exist.

`cpause1`, `cwalk`, and `crun` are vanilla behavior aliases. New actions are
additive namespaced registrations allocated through the Custom Animation Patch;
the builder never replaces unrelated vanilla animation slots.

Imported DCC images are vertically reoriented once when their build copies are
encoded because Odyssey MDX texture coordinates use the opposite row
orientation from the source image convention used by this workflow. The
project stores an explicit per-material opt-out for images already authored in
KOTOR orientation, and the UI previews the result. Source bytes are never
rewritten. A material marked `cutout` receives `blending punchthrough` and
`alphatest 0.5` when no authored TXI is present; authored TXI text always takes
precedence.

KOTOR runtime-height correction is authored once on the base model's
`heightdummy`. Odyssey animation position controllers are local deltas added to
that rest position, so every animation keeps the same `heightdummy` hierarchy
edge without repeating the base translation. Serialized-model validation rejects
any nonzero animation position delta on this helper; otherwise playback would
apply the correction twice and lift the creature above the floor.

Creature combat aliases are derived from verified Odyssey creature models, not
guessed from source clip names. The Zakkeg baseline currently recognizes
`m0a1`, `m0a2`, `g0a1`, `g0a2`, `cdamages`, `cdodgeg`, `creadyr`,
`creadyrtw`, `cwalkinj`, `ckdbck`, `ckdbcklp`, `cgustandb`, `cdie`, `cdead`,
`ctaunt`, `cvictory`, `chturnl`, and `chturnr`. A suggested mapping is a UI
decision awaiting confirmation, never an implicit replacement.

## Behavior-template and UTC contract

The behavior service indexes effective installed UTC resources with the same
precedence the game uses and writes a machine-readable catalog report. Every
known character can therefore serve as a reviewable starting template without
hardcoding a small built-in list. Catalog rows include TLK-resolved name,
source scope, module-only status, faction, attributes, vitality, challenge
rating, perception, classes, feats, equipment, sound set, conversation, and
all fourteen creature event hooks.

Applying a template clones its GFF and preserves unknown fields. It replaces
only project-owned identity, appearance-token, and explicitly edited behavior
fields. Custom NSS is compiled through the KOTOR scripting service, the NCS is
read back before packaging, and source-only hooks are rejected. The optional
spawn helper follows the same compile/read-back gate. The generated UTC keeps
the selected template's class, statistics, equipment, sounds, faction, and
inherited event scripts while using the custom model's merge-resolved
appearance row.

`FactionID` is serialized as the `UInt16` used by stock K1/K2 UTC templates.
The blank-creature contract and the donor-template path share that type; using
`UInt32` can make the engine ignore the requested faction and display a
friendly/neutral health bar.

The Borhek fixture starts from global K2 `c_zakkeg01`, not the module-bound
`c_zakkeg002`. Its custom attacked hook delegates to `k_def_attacked01` and
then queues an explicit attack on the last attacker. Other hooks retain the
Zakkeg baseline unless the user changes them in the visible event-hook editor.

## Native creature-sound contract

Custom creature audio must use KOTOR's SSF/TLK/soundset route, not wrappers
around UTC AI hooks. Retail testing rejected the initial wrapper design:
`ExecuteScript` starts another script invocation and does not safely preserve
event-specific values such as the last attacker or perceived target. Wrapping
`ScriptAttacked` therefore prevented the Zakkeg-derived combat script from
retaining a target even though the MDL still contained `m0a1` and `m0a2`.

The accepted build contract is symbolic until exact-install preview:

1. Project data stores each cue, portable source WAV, SHA-256, and output
   ResRef. Validation accepts only readable mono 16-bit PCM at 11025, 22050, or
   44100 Hz.
2. Behavior preparation packages WAVs and maps cues to native SSF slots:
   battle cries, attack grunts, pain grunts, low health, and death. It never
   emits a sound wrapper or UTC hook override.
3. Build writes a merge instruction rather than hardcoding live StrRefs or a
   `soundset.2da` row.
4. Preview reads the selected installation, appends or reuses only
   Ghost-Studio-owned `dialog.tlk` entries for the WAV ResRefs, emits a
   readback-validated 40-entry SSF, upserts one `soundset.2da` row, and patches
   the UTC `SoundSetFile` UInt16 to the resolved row.
5. Exact preview includes the game-root `dialog.tlk` target. Install backs up
   that global file before replacement, hashes every candidate and target, and
   Restore returns the prior TLK/2DA/SSF/WAV/UTC bytes or fails closed if a
   target changed later.

This route deliberately leaves spawn, notice, attacked, damaged, heartbeat,
end-round, blocked, and death hooks direct. Sound selection cannot silently
change faction logic or combat behavior.

The beginner runtime route does not require a console command. When selected,
the install plan names a K2 test module, unique Ghost Studio placement tag,
position, and bearing. Preview reads the live `plcaa.mod`, replaces only an
earlier placement with the same Ghost Studio tag, otherwise clones one existing
creature placement, chooses the nearest deterministic open test position when
another placement occupies the requested coordinates, and rebuilds the MOD
through the canonical Scene pipeline.
It then proves that the resource key set is identical, every non-GIT resource
is byte-identical, all unrelated creature placements are structurally
identical, and every non-creature GIT field is structurally identical. Install
backs up the live module and cached `currentgame/plcaa.mod`, clears the cache,
and records both operations in the same guarded restore session as the Override
files. A live-module or cache change after preview stops installation.
The visible test checklist requires loading a save outside the test module
before entering it. A save made inside `plcaa` contains a serialized creature
instance and can preserve an older model or faction independently of the newly
installed UTC.

## Persistence and safety contract

The human-readable project stores builder mode, target game, portable source
references and hashes, coordinate conversion, scale/ground decisions, selected
root/export nodes, skin repairs, animation sources/mappings/preparation,
materials/textures, gameplay/UTC/appearance settings, custom registrations,
build destination, and last validation/build evidence. Missing relocated assets
are reported rather than rewritten to machine-specific absolute paths.

Source FBX, Blend, textures, videos, game files, and extracted evidence remain
read-only. Converted files are written to a project build directory. Saves and
builds are atomic where practical and never silently overwrite a different
project or unrelated Override file.

An existing build directory is reusable only when its report identifies the
same project and every report-owned output still matches its recorded hash.
Rebuild removes only those verified owned files and preserves unlisted files.
Preview creates candidates outside Override and may run while the game is
open. Install and restore recheck the executable, candidate files, live target
hashes, and Windows process state; they fail closed if the state cannot be
verified. Replaced targets receive byte-for-byte backups and a session
manifest before any candidate is committed.

## Borhek golden fixture

The first end-to-end fixture is the preserved Borhek source pipeline and its
current evidence in KOTOR Patch Manager. The verified reference milestone has:

- 40 source hierarchy nodes, 10 source meshes, 2,246 vertices, and 3,058
  triangles;
- 15 exported skin nodes with a maximum 12-entry Odyssey bone palette;
- 58 reloaded Odyssey nodes;
- semantic `cpause1`, `cwalk`, and `crun` clips plus additive `kpm_bor_*`
  actions;
- verified combat clips `m0a1`, `m0a2`, `cdamages`, `cdie`, `creadyr`,
  `creadyrtw`, and `ctaunt`, plus a Zakkeg-derived hostile UTC and compiled
  attacked/spawn scripts;
- MDL SHA-256
  `49063631c4b9f3b4db80f6c6e0036430a3235c2058341a7755b1cab00a0da491`;
- MDX SHA-256
  `a2d0ceb85de8403672686777df4b8c1c634f36fd93f90c16df4a8f5a51b8d89d`.

Those hashes are comparison evidence, not an assumption that the newest
texture-corrected build must be byte-identical. Completion requires structural
and behavioral equivalence, source byte identity, merge-safe appearance and UTC
generation, a non-colliding registry, and visible KOTOR II proof in `plcaa` of
ground height, texture wrapping, idle, walk, run, turning, reload safety, and
stable skinning. Hostile proof also requires a red target health bar on a fresh
module instance; KOTOR II's cyan target-name text is normal for hostile targets.
Audio proof additionally requires audible native battle/attack/pain/death cues
without losing either `m0a1` or `m0a2` combat playback.

The first 2026-07-19 Ghost Studio UI build was installed for comparison but did
not pass visible runtime acceptance. Its reloaded model contained 59 Odyssey
nodes because it retained `godnode` below a newly-added `c_borhek` root, and it
wrote 9,174 flattened skin rows. It included `cpause1`, `cwalk`, `crun`,
`m0a1`, `m0a2`, `cdamages`, `cdie`, `creadyr`, `creadyrtw`, and `ctaunt`.
Failure-candidate hashes were:

- MDL SHA-256
  `48d28199802aa0c63bb5fdd2712e21d8a039acbd4c5d11410971c7bd7bbc391d`;
- MDX SHA-256
  `8b850510d2d508c801c32af98760088fd2c201cf09ccaaf3c0a10b890d947bad`;
- compiled attacked NCS SHA-256
  `530365794e75973c9b018a2cf1d97a25492bb363e4e2f7a0081fb25af065ca0d`;
- compiled spawn NCS SHA-256
  `20b9a61f8f6a0413a040ba10bb03f740cd912279c68fd1fb3d60b301450ddd49`.

The corrected headless comparison candidate absorbs `godnode`, reloads with
58 model nodes and 42 nodes per animation, restores all fifteen prototype skin
part counts, writes only the meaningful `root_joint` position track in each
mapped clip, and produces a 231,700-byte MDX. This is structural evidence only;
the candidate still requires a fresh build/install through the visible Debug
UI and user-confirmed KOTOR playback before it becomes completion evidence.

The exact-install preview resolved `c_borhek` to row 724 in the live test
installation and patched the UTC to that row. Row 724 is evidence about that
specific live table, not a constant: another installation must resolve the row
again. The package report remains the authority for all texture, source,
registry, validation, and output hashes.

## Completion gates

Exported files alone are not completion. Focused unit and integration tests must
cover every handoff rule, the native builder must retain its existing behavior,
and the workflow must be usable without console commands, manual JSON edits,
hardcoded 2DA rows, direct MDL surgery, or source changes. Each limitation,
required convention, output hash, and runtime observation is added to the
repository knowledge base as it is discovered.
