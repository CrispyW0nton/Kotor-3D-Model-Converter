# Custom Rigged Character Builder

Use this workflow when your FBX already has its own skeleton and skin weights.
It is separate from **Native KOTOR Character**, which keeps the existing KOTOR
template-rig and supermodel workflow unchanged.

## Start a project

1. Open Character Builder and choose **Custom Rigged Character**.
2. Enter a friendly creature name and a lowercase KOTOR resource name of at
   most 16 characters.
3. Choose the primary FBX, optional animation FBX files, texture folder, output
   folder, and KOTOR game folder.
4. Select **Import and inspect**. Ghost Studio records SHA-256 fingerprints and
   reads the sources without changing them.

If an FBX contains more than one armature or root, choose exactly one deform
hierarchy and import again. Ghost Studio never merges separate rigs silently.
The selected authoring root becomes the resource-named Odyssey model root; it
is not exported as a second wrapper node. This preserves the chosen hierarchy
while matching the root layout used by working custom creatures.

## Review the creature

- **Rig inspection** shows the real imported model and hierarchy. Blocking
  errors explain missing parents, unresolved skin bones, bad bind matrices,
  invalid weights, or unsupported animated transforms. Safe repairs describe
  exactly what they change.
- **Scale, facing, pivot, and ground contact** compares the model with a 1.8
  unit human reference. Use **Detect lowest contacts**, then **Place contacts on
  ground**. Ghost Studio also detects a separate KOTOR runtime-height correction
  from the imported root joint and applies it automatically. Both offsets are
  shown in the project; source vertices are untouched.
- **Animation library** lists each action's duration, frames/rate, looping,
  root motion, and animated-bone count. Suggestions are not exported until you
  confirm them. Normal KOTOR movement uses `cpause1`, `cwalk`, and `crun`.
  Other actions stay unassigned or receive a namespaced additive ID through
  the verified Custom Animation Patch.
- **Animation preparation** provides live source/result viewports for trim,
  speed, retiming, loop, root-motion, and sampling decisions. A different
  source skeleton is blocked until an explicit retarget mapping is reviewed.
- **Materials, textures, and UVs** shows the source image, KOTOR approximation,
  and UV checker. **Orient imported image for KOTOR (recommended)** performs
  the one DCC-to-Odyssey row conversion needed by imported images and shows the
  result before building; turn it off only for an image already authored in
  KOTOR orientation. Choosing **Cutout / punch-through** automatically adds the
  standard KOTOR edge-transparency settings, while Advanced TXI text remains an
  explicit override. Repeated UVs are preserved, and TGA/TPC/TXI copies are
  written only inside the build package.

## Give the creature game behavior

Open **KOTOR gameplay integration** after the model and animations are ready.
The **Known character templates** list is built from every effective UTC that
Ghost Studio can find in the selected installation, including Override,
modules, and the stock game archives. Search by the in-game name or resource
name, then review the template's faction, attributes, hit points, challenge
rating, class, feats, equipment, sounds, and event scripts before applying it.
Module-only records are clearly marked so they are not mistaken for reusable
global templates.

For Borhek, choose **Use Zakkeg combat baseline**. This copies the verified
global `c_zakkeg01` UTC gameplay values while keeping Borhek's own resource
name, appearance, model, and textures. The quick action also suggests the
verified creature-combat animation aliases: `m0a1` and `m0a2` for attacks,
`cdamages` for a hit reaction, `cdie` for death, `creadyr`/`creadyrtw` for
combat readiness, and `ctaunt` for its roar. Suggestions remain visible and
editable until confirmed.

Each UTC event hook is shown separately. Choose **Inherit template** to keep
the stock behavior, **None** to clear it intentionally, or **Custom script** to
write a project-owned action. Ghost Studio compiles custom NSS inside the
builder, reads the NCS back for verification, and packages only compiled
runtime bytecode. Borhek's attacked hook first runs `k_def_attacked01`, then
explicitly attacks `GetLastAttacker()`. The optional advanced spawn helper is
also compiled and verified; for this fixture it is `spawn_c_borhek.ncs`.

For beginner testing, enable **Place one temporary test creature in PLCaa
DevRoom (no console needed)**. Ghost Studio clones one existing placement,
changes only the clone's UTC reference, tag, position, and facing, and verifies
that every other creature, GIT field, and non-GIT module resource remains
unchanged. The resulting `plcaa.mod` candidate is shown in the exact install
preview and is never written before confirmation. If the requested spot is
already occupied, preview chooses the nearest open test spot and explains the
adjustment instead of overlapping or moving the existing creature.

Applying a template never edits the installed UTC. Unknown GFF fields are
preserved when the cloned UTC is written, the final appearance row is resolved
from the live table during install preview, and the generated creature can be
spawned again by its own `c_borhek` resource name after a game restart.

## Build and install safely

Run **complete preflight**, review every warning, and explicitly accept any
warnings you understand. **Build KOTOR package** creates a self-contained
MDL/MDX pair, reload-validates it, converts textures, writes a UTC template,
and writes a merge instruction for a dedicated `appearance.2da` row. Reports
record sources, repairs, validation, limitations, and output hashes.

On **Install and test**:

1. Select **Preview exact install**. Preview is read-only and remains available
   while KOTOR is running.
2. Review every target, current hash, candidate hash, and backup status. If the
   DevRoom option is enabled, this includes `Modules/plcaa.mod` and any cached
   `currentgame/plcaa.mod` that must be backed up and cleared.
3. Close KOTOR before selecting **Install with backup**. Installation stops
   safely if Ghost Studio cannot prove the game is closed.
4. Select **Install with backup** only if the list is correct.
5. Use **Restore previous files** with the recorded install session to undo the
   operation, including the prior live/cached PLCaa modules. Restore stops if a
   file changed after installation.

The installer resolves the live appearance row instead of hardcoding a row
number. It never replaces vanilla animations. Additive actions require the
supported executable fingerprint and the Custom Animation Patch installed by
KOTOR Patch Manager; fingerprint checks are never bypassed.

## In-game checklist

Confirm visibility, ground height, texture wrapping, idle, walking while
moving, running while moving quickly, turning and skin stability, module
reload, and any explicitly requested custom action. For a hostile creature,
also confirm target perception, combat start, both attacks, damage reaction,
round-end behavior, death, and a second spawn after restarting the game. A
successful file build is not runtime proof.

## Portable project and reports

Projects use `.ghostcharacter.json`. Paths are stored relative to the project
when possible and missing relocated files are reported. Automatic save never
replaces a different project. Rebuilding into an occupied output folder stops
instead of silently overwriting it.

Package reports include a generation timestamp, which is intentionally
nondeterministic audit metadata. Model, texture, manifest, patch, and UTC bytes
are deterministic for identical inputs and settings; their SHA-256 hashes are
recorded independently. The base model owns the automatic KOTOR runtime-height
helper. Animation clips inherit that base placement without adding the same
height again; reload validation rejects a clip that would lift the creature a
second time.

FBX preview extraction may temporarily flatten a mesh into one record per
triangle corner so UV seams and split normals remain visible. Ghost Studio also
retains each corner's original FBX vertex identity. The Odyssey build restores
that indexed skin before palette splitting, avoiding redundant skin rows while
preserving faces, UVs, weights, and hard edges.
