# Python Terminal Cheatsheet

This file records useful commands for the embedded GhostRigger Python terminal.
When terminal helpers or practical terminal workflows are added or changed,
update this file so future agents and users can reuse them.

The terminal is embedded in the bottom Output Log area. Commands run in the
live Qt application process, so they can inspect and operate on the currently
loaded model.

## Built-In Context

- `window` - the main `QtGhostRiggerMainWindow` instance.
- `main_window` - alias for `window`.
- `viewport()` - returns the main viewport widget.
- `model()` - returns the currently loaded/selected model, or `None`.
- `selected_model()` - alias for `model()`.

## Inspect The Current Model

```python
model()
```

```python
model().name
```

```python
len(model().mesh_nodes())
```

```python
len(model().all_nodes())
```

```python
[node.name for node in model().bone_nodes()[:20]]
```

## Animation Commands

List animation names on the selected model:

```python
animation_names()
```

Select an animation in the Animation Library panel without playing it:

```python
select_animation("pause1")
```

Play an animation:

```python
play_animation("walk")
```

Play an animation with looping enabled:

```python
play_animation("dance", loop=True)
```

Stop playback:

```python
stop_animation()
```

Seek through the selected/current animation by percent:

```python
seek_animation(50)
```

## Selected Animation FBX Exports

Export a KOTOR model into a Unity project and embed only the named effective
local or inherited animation sets. Repeat `--animation` once per take:

```powershell
python scripts/export_kotor_model_for_unity.py --game k1 --game-dir "C:\Games\KOTOR" --resref pmbam --unity-project "C:\Projects\MyUnityProject" --asset-subdir "Assets\Characters\PMBAM" --animation walk --animation talk
```

Use `--no-animations` instead to export only the mesh and rig. Omitting both
options preserves the model's existing local animation blocks.

Export the same selected takes with the Unreal Engine compatibility profile
through the embedded KotorMCP bridge:

```python
import asyncio
from kotormcp.tools import handle_tool

async def export_unreal_fbx():
    result = await handle_tool("ghostrigger_export_model_for_unreal", {
        "game": "k1",
        "game_path": r"C:\Games\KOTOR",
        "resref": "pmbam",
        "output_path": r"C:\Exports\pmbam_unreal.fbx",
        "animation_names": ["walk", "talk"],
    })
    print(result["text"])

asyncio.run(export_unreal_fbx())
```

Pass an empty `animation_names` list for a mesh-and-rig-only Unreal FBX.

## Drexl Re-UV Runtime Proof

The Drexl replacement package is staged in the local KOTOR II Override folder.
Use these after KOTOR II is running with cheats enabled.

Start a KotorMCP live debug-event log before launching KOTOR II:

```python
import asyncio, json
from kotormcp.tools import handle_tool

async def start_kotor_log():
    result = await handle_tool("kotor_log_start", {
        "game": "k2",
        "session_label": "drexl-live-test",
        "wait_for_process": True,
        "duration_seconds": 180,
        "asset_resrefs": ["c_drexlf", "appearance"],
    })
    print(result["text"])

asyncio.run(start_kotor_log())
```

Analyze the latest KOTOR live log and annotate crash offsets through Ghidra:

```python
import asyncio
from kotormcp.tools import handle_tool

async def analyze_latest_kotor_log():
    result = await handle_tool("kotor_log_analyze", {
        "game": "k2",
        "annotate_with_ghidra": True,
        "ghidra_program": "/TSL/k2_win_steam_aspyr_swkotor2.exe",
    })
    print(result["text"])

asyncio.run(analyze_latest_kotor_log())
```

KOTOR II does not expose a `dm_spawncreature` console command. For the KPM
Issue #98 Drexl proof, close the game and place the unique fixture directly in
the PLCaa GIT:

```powershell
py "C:\Users\NewAdmin\Documents\GDeveloper\Workspaces\Kotor-Patch-Manager\tools\stage_k2_plcaa_drexl_fixture.py" --install
```

Then use the real KOTOR II console command:

```text
warp plcaa
```

After capturing screenshot or video evidence, record the proof:

```powershell
python scripts/record_drexl_runtime_game_proof.py --proof-manifest "C:\Users\NewAdmin\Documents\KotorMods\HighFidelityKotorCharacters\Drexl\c_drexlf_override_package\c_drexlf_runtime_game_proof_manifest.json" --evidence "C:\path\to\drexl_runtime_evidence.png" --tester "LordVaderCW" --game-launches-with-override --ambient-drexl-spawns --new-texture-visible --uv-alignment-ok --idle-animation-ok --walk-animation-ok --scale-orientation-ok --camera-hook-ok
```

## KOTOR Live Proof Hook And Logger

Install or verify the GhostRigger DirectInput proxy hook for KOTOR 1:

```python
import asyncio
from kotormcp.tools import handle_tool

async def install_k1_hook():
    result = await handle_tool("kotor_dinput_hook_install", {"game": "k1"})
    print(result["text"])

asyncio.run(install_k1_hook())
```

Install or verify the same hook for KOTOR 2:

```python
import asyncio
from kotormcp.tools import handle_tool

async def install_k2_hook():
    result = await handle_tool("kotor_dinput_hook_install", {"game": "k2"})
    print(result["text"])

asyncio.run(install_k2_hook())
```

Preflight a Map Studio warp proof and require the hook:

```python
import asyncio
from kotormcp.tools import handle_tool

async def preflight_tst_light(game):
    result = await handle_tool("kotor_prepare_save_warp_test", {
        "game": game,
        "target_module": "tst_light",
        "require_dinput_hook": True,
    })
    print(result["text"])

asyncio.run(preflight_tst_light("k1"))
```

Queue the hidden-console warp through the DirectInput hook:

```python
import asyncio
from kotormcp.tools import handle_tool

async def hook_warp(game):
    result = await handle_tool("kotor_dinput_hook_send", {
        "game": game,
        "text": "warp tst_light",
        "open_console": True,
        "press_enter": True,
        "reset_first": True,
    })
    print(result["text"])

asyncio.run(hook_warp("k1"))
```

Start a live crash log for KOTOR 1 and analyze it with Ghidra addresses:

```python
import asyncio
from kotormcp.tools import handle_tool

async def k1_live_log():
    start = await handle_tool("kotor_log_start", {
        "game": "k1",
        "session_label": "tst-light-k1",
        "wait_for_process": True,
        "duration_seconds": 180,
        "asset_resrefs": ["tst_light"],
    })
    print(start["text"])

asyncio.run(k1_live_log())
```

Copy one animation clip over another on the selected model:

```python
override_animation("pause1", "dance")
```

This deep-copies `dance`, renames the copy to `pause1`, replaces the existing
`pause1` clip if present, and refreshes the Animation Library.

Add a copied animation under a new name:

```python
override_animation("my_custom_pause", "pause1")
```

## Viewport Helpers

Frame the current model:

```python
viewport().frame_all()
```

Reset the viewport camera:

```python
viewport().reset_camera()
```

Clear any active animation pose from the viewport:

```python
viewport().clear_animation_pose()
```

Create a focused custom viewport widget module:

```python
create_viewport_widget("Orbit Gizmo")
```

Create a viewport behavior mixin scaffold:

```python
create_viewport_widget("orbit selection", kind="mixin")
```

The scaffold is written under `src/gui/viewports/viewport_core/widgets/` and
returns the created path, class name, module name, and next steps. Use
`public_export=True` when the new widget should become part of the public lazy
viewport API.

## Logging

Write to the Output Log from the terminal:

```python
window._log("Hello from the Python terminal", "info")
```

## Map Studio Smoke Workflows

Capture a focus-safe stock-sky proof from an already running GhostStudio IPC
server. This imports K1 Taris into an empty Map Studio project, captures the
real canvas with its sky hidden and shown, verifies the expected sky textures,
and refuses to steal foreground focus or overwrite an existing project:

```powershell
$proofRoot = [IO.Path]::GetFullPath((Join-Path (Get-Location) "Saved\VisibleProof\map_studio_sky"))
New-Item -ItemType Directory -Force -Path $proofRoot | Out-Null

$body = @{
    game = "K1"
    module_resref = "tar_m02aa"
    modules_dir = "C:\Program Files (x86)\Steam\steamapps\common\swkotor\Modules"
    before_path = (Join-Path $proofRoot "01_without_sky.png")
    after_path = (Join-Path $proofRoot "02_with_sky.png")
    activate = $false
    # Positive proof requests are normalized to the full five-second renderer
    # residency window so stock sky textures have time to decode and upload.
    settle_ms = 5000
    expected_room_resref = "m02aa_sky"
    expected_backdrop_surface_count = 6
    expected_textures = @{
        lts_sky0001 = @(512, 512)
        lts_sky0002 = @(512, 512)
        lts_sky0003 = @(512, 512)
        lts_sky0004 = @(512, 512)
        lts_sky0005 = @(512, 512)
    }
} | ConvertTo-Json -Depth 5
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:7001/api/map_studio_visual_proof -ContentType "application/json" -Body $body
```

The resulting images prove GhostStudio viewport behavior only. A KOTOR warp
and live log are still required before treating the sky or lighting as working
in game.

Stage both `grdev01` Map Studio smoke-module variants for manual KOTOR testing:

```powershell
python scripts/stage_grdev01_smoke_suite.py --output-dir artifacts/map_studio/grdev01_variant_suite
```

Print the same result as JSON for automation:

```powershell
python scripts/stage_grdev01_smoke_suite.py --output-dir artifacts/map_studio/grdev01_variant_suite --json
```

Stage only the floor-plan/opening variant:

```powershell
python scripts/stage_grdev01_smoke_suite.py --output-dir artifacts/map_studio/grdev01_floor_plan_only --no-rectangular
```

Build and safely install one selected `grdev01` variant into a KOTOR `Modules`
folder for the `warp grdev01` test:

```powershell
python scripts/install_grdev01_smoke_variant.py --variant floor-plan --game-modules-dir "C:\Path\To\KOTOR\Modules"
```

Preview the same install without copying files:

```powershell
python scripts/install_grdev01_smoke_variant.py --variant rectangular --game-modules-dir "C:\Path\To\KOTOR\Modules" --dry-run
```

After a real in-game `warp grdev01` test, record proof with the evidence file
and every verified acceptance check:

```powershell
python scripts/record_grdev01_smoke_proof.py --proof-manifest artifacts/map_studio/grdev01_install/floor_plan_opening/grdev01_in_game_smoke_manifest.json --evidence "C:\Path\To\grdev01-proof.png" --tester LordVaderCW --module-loads-in-game --player-spawns-on-floor --test-placeable-visible --player-can-walk-on-floor
```

Audit the current proof state before or after recording evidence:

```powershell
python scripts/check_grdev01_smoke_status.py --proof-manifest artifacts/map_studio/grdev01_install/floor_plan_opening/grdev01_in_game_smoke_manifest.json --game-modules-dir "C:\Path\To\KOTOR\Modules"
```

Each staged variant produces its own `grdev01.mod`. Copy one variant at a time
into the KOTOR `Modules` folder, run `warp grdev01`, and record screenshot or
video evidence before treating it as game-tested.

## Legacy Module Recovery And Cross-Game Candidates

Preflight the non-destructive modern KOTORMax fallback for the surviving
Vul803 Max 9 scenes. This writes a JSON evidence report and makes no install or
scene changes when 3ds Max is absent:

```powershell
py -3.14 scripts/recover_vul803_max_scenes.py --preflight
```

After installing licensed 3ds Max, run the fallback in a fresh evidence
directory. Its output is visual forensics; use
`scripts/kotormax/README.md` for the preferred isolated NWMax 0.8 b60 room-
partition workflow:

```powershell
py -3.14 scripts/recover_vul803_max_scenes.py
```

Compile the surviving Vul803 `01a` visual ASCII with the original `01b` AABB
source into a controller-free K2 structural candidate. Repeat with `--game K1`
and a separate output directory for K1:

```powershell
py -3.14 scripts/compile_nwmax_room_candidate.py --room vul803_01a --game K2 --render-ascii "C:\Users\NewAdmin\Documents\KotorMods\Modules\Q_SellOut\Extracted\LavaPlanet_2011-12-26\LavaPlanet\LavaPlanet\Vul803_01a.mdl" --walkmesh-ascii "C:\Users\NewAdmin\Documents\KotorMods\Modules\Q_SellOut\Extracted\LavaPlanet_2011-12-26\LavaPlanet\LavaPlanet\Vul803_01b.mdl" --output "C:\Users\NewAdmin\Documents\KotorMods\Modules\Converted\WalkmeshAudit\GeneratedCandidates\vul803\NWMaxCompileVerified\K2"
```

This compiler runs MDLOps only as a compatibility audit and promotes Ghost
Studio's zero-controller MDL/MDX plus its validated floor-only WOK. A passing
report is still not retail-game proof.

Convert one recovered room through MDLOps 1.0.2 into an isolated K1 or K2
worktree. The command never overwrites the downloaded source unless
`--overwrite` is explicitly supplied for an existing candidate directory:

```powershell
py -3.14 scripts/repair_legacy_modules.py room --room myroom_01a --game K2 --mdl "C:\Recovered\myroom_01a.mdl" --mdx "C:\Recovered\myroom_01a.mdx" --wok "C:\Recovered\myroom_01a.wok" --mdlops "Saved\ExternalTools\mdlops\mdlops.exe" --output "C:\Candidates\myroom\K2\Rooms"
```

Assemble repaired rooms with preserved or explicitly supplied module metadata.
The workflow generates absent LYT/VIS/PTH only where the result is derivable,
patches WOK perimeter records, and blocks ambiguous resource collisions:

```powershell
py -3.14 scripts/repair_legacy_modules.py module --module myroom --game K2 --rooms "C:\Candidates\myroom\K2\Rooms" --output "C:\Candidates\myroom\K2\Candidate" --source-mod "C:\Recovered\myroom.mod" --lyt "C:\Recovered\myroom.lyt" --vis "C:\Recovered\myroom.vis"
```

Stage exact vanilla texture dependencies from one game only when the target
game does not already provide them. TXI environment/bump dependencies are
followed automatically and every copied TPC receives hash/provenance evidence:

```powershell
py -3.14 scripts/repair_legacy_modules.py textures --source-root "C:\Program Files (x86)\Steam\steamapps\common\swkotor" --target-root "C:\Program Files (x86)\Steam\steamapps\common\Knights of the Old Republic II" --texture LMA_wall09 --texture LMA_tab01 --output "C:\Candidates\myroom\K2\VanillaTextures"
```

Prove the actual Map Studio API can import the candidate, convert every stock
room to editable geometry, save KMAP, and reopen it through a fresh controller:

```powershell
py -3.14 scripts/prove_legacy_module_mapstudio_roundtrip.py --game K2 --game-root "C:\Program Files (x86)\Steam\steamapps\common\Knights of the Old Republic II" --module "C:\Candidates\myroom\K2\Candidate\Modules\myroom.mod" --kmap "C:\Candidates\myroom\K2\MapStudioProof\myroom.kmap" --report "C:\Candidates\myroom\K2\MapStudioProof\myroom.mapstudio-roundtrip.json"
```

These commands establish structural and editor compatibility only. Install the
exact resulting MOD and complete a manual warp, movement, camera, texture, and
transition test in each target game before calling a candidate game-compatible.

## Map Studio Targeted Refresh Timing

After dragging or property-editing a placed GIT object or room light in Map
Studio, read the last targeted commit-refresh duration from the embedded
terminal (T2904; the broad `_refresh_all` path is only used for placement
add/remove, undo/redo, and load/save):

```python
ms = window.module_editor_window
(ms._last_map_studio_gameplay_refresh_ms, ms._last_map_studio_geometry_refresh_ms)
```

Confirm the combined preview model was NOT rebuilt by a transform commit
(cache hit stays true and the elapsed preview time stays near zero):

```python
c = window.module_editor_window.controller
(c.last_map_studio_preview_cache_hit, c.last_map_studio_preview_elapsed_ms)
```

## Mesh Tools IPC

Create a cube in the active KMAX scene through the mesh tool command route:

```powershell
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:7001/api/mesh_tool_command -ContentType "application/json" -Body '{"command":"create_cube","options":{"name":"IPC_Cube","dimensions":[2,2,2],"position":[0,0,0],"pivot_preset":"center","material":"default","grid_snap":true}}'
```

Snap the selected object or mesh element to a 0.5-unit grid on X/Y/Z:

```powershell
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:7001/api/mesh_tool_command -ContentType "application/json" -Body '{"command":"snap_to_grid","options":{"grid_size":0.5,"axes":["x","y","z"]}}'
```

Assign a simple material override and run topology validation:

```powershell
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:7001/api/mesh_tool_command -ContentType "application/json" -Body '{"command":"assign_material","target":{"id":"selected"},"options":{"slot":0,"material":"metal_floor"}}'
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:7001/api/mesh_tool_command -ContentType "application/json" -Body '{"command":"validate_mesh","target":{"id":"selected"}}'
```

## Unreal / FBX Animation Injection

Extract an Unreal humanoid FBX clip with Blender, retarget it to a KOTOR model,
resolve inherited animation slots from the selected game installation, write
MDL/MDX, and require writer round-trip verification before reporting PASS:

```powershell
py -3.14 scripts/inject_animation.py --source-fbx "C:\Path\To\UnrealAnimation.fbx" --target-mdl "C:\Path\To\pmbam.mdl" --target-mdx "C:\Path\To\pmbam.mdx" --slot victory --game K1 --game-dir "C:\Program Files (x86)\Steam\steamapps\common\swkotor" --output "Saved\RetargetProof\ue_to_kotor" --write-mdl
```

Use `--game K2` with the KOTOR 2 installation for TSL targets. A successful
headless readback is still not an in-game animation proof; trigger the exact
written slot in the target game before shipping it.
