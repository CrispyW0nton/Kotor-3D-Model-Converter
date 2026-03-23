# Blender Integration

This page documents the current Blender-backed workflow for Holocron Toolset and the upstream
[`OldRepublicDevs/kotorblender`](https://github.com/OldRepublicDevs/kotorblender) add-on.

## Goals

The Blender integration exists to give Toolset users a second editing path for 3D-heavy workflows:

- inspect and edit **LYT room layouts**
- inspect and edit **GIT instances** (creatures, placeables, doors, waypoints, etc.)
- preview real room/walkmesh geometry in Blender instead of relying entirely on the built-in Python viewport
- bring in external royalty-free assets through Blender’s native importers before converting/exporting them into KotOR-compatible resources

## Supported Blender / add-on versions

- **Recommended Blender version:** `4.2 LTS`
- **Other upstream-supported versions:** `3.6`, `5.0`
- **Upstream add-on:** `kotorblender 4.0.4`

## How the Toolset integration works

The Toolset no longer assumes a bundled vendor checkout of `kotorblender`.

Instead it now supports the following source discovery order:

1. a custom `io_scene_kotor` source path from the `KOTORBLENDER_SOURCE_PATH` environment variable
2. a local repository checkout such as `vendor/kotorblender/io_scene_kotor`
3. an adjacent checkout such as `kotorblender/io_scene_kotor`
4. an auto-downloaded cache of the upstream `OldRepublicDevs/kotorblender` GitHub repository

When the Toolset installs the add-on, it also injects a **Holocron IPC overlay** into the installed
`io_scene_kotor` package. This overlay hosts the Toolset’s JSON-RPC bridge inside Blender without
requiring Blender to import the Toolset’s full Python environment directly.

## What the live bridge currently supports

The Toolset ↔ Blender bridge supports:

- Blender process launch and add-on enablement
- JSON-RPC ping/version negotiation
- loading a Toolset session into Blender
- creating/removing/updating GIT instances
- room / door hook / track / obstacle sync
- selection synchronization
- transform synchronization
- save/export of updated LYT + GIT state back through the bridge
- background-mode smoke testing for the bridge runtime

## External asset import pipeline

While Blender mode is active, dropping supported external files onto the Toolset’s 3D renderer will
forward them into the active Blender session.

### Supported external imports

#### 3D asset formats

- `.obj`
- `.fbx`
- `.gltf`
- `.glb`
- `.dae`

#### Texture/image formats

- `.png`
- `.jpg`
- `.jpeg`
- `.tga`
- `.tif`
- `.tiff`
- `.bmp`
- `.webp`

### Important note

The current Toolset integration handles **import into Blender**. Converting the edited result into
KotOR runtime resources still relies on the normal `kotorblender` export flow (for example
`kb.mdlexport`) plus PyKotor packaging/conversion steps for textures and module resources.

In other words:

- **drag/drop into Blender:** supported
- **edit in Blender with Toolset session active:** supported
- **export imported meshes back out as KotOR MDL/MDX:** supported through the live bridge for minimal trimesh-style exports
- **full packaging back into modules/kits:** still uses the standard `kotorblender` exporters plus PyKotor packaging/conversion steps

### Minimal model export support

The bridge can now take an imported mesh object (for example from `.obj`) and wrap it in a minimal
KotOR model root so it can be exported as:

- `.mdl`
- `.mdx`

This path is intended for simple trimesh-style content and automated validation, not as a substitute
for all manual authoring features inside Blender.

## Walkmesh generation behavior

The Toolset’s procedural walkmesh generation path was upgraded so that it now prefers **real room
walkmesh templates** whenever they are available.

### Current behavior

When generating a layout walkmesh:

1. the Toolset looks for matching `WOK` resources by room model name
2. if a template exists, it deep-copies that walkmesh and **re-anchors** it at the requested room position
3. if no template exists, the Toolset falls back to the older placeholder floor quad

This means the “procedural” path now preserves:

- real face materials
- real room extents
- real per-face transition metadata

instead of always synthesizing a generic square floor.

## Testing

### Toolset unit tests

```bash
QT_QPA_PLATFORM=offscreen uv run pytest --import-mode=importlib \
  Tools/HolocronToolset/tests/blender/test_blender_integration.py -q
```

### Live bridge runtime smoke tests

Set `BLENDER_BIN` to a usable Blender executable and run:

```bash
QT_QPA_PLATFORM=offscreen BLENDER_BIN="/path/to/blender" uv run pytest --import-mode=importlib \
  Tools/HolocronToolset/tests/blender/test_blender_runtime_bridge.py -q
```

These runtime tests validate:

- bridge launch
- ping/version handshake
- module/session roundtrip
- external `.obj` import into Blender

### Walkmesh renderer tests

```bash
QT_QPA_PLATFORM=offscreen uv run pytest --import-mode=importlib \
  Tools/HolocronToolset/tests/gui/widgets/test_walkmesh_renderer.py -q
```

## Current limitations

- The bridge is focused on the **Toolset editing session**, not on replacing every Blender-native workflow.
- External asset import is supported, but end-to-end “import arbitrary asset → automatically ship as final KotOR resource” is still a guided pipeline rather than a one-click conversion path.
- Engine-level documentation updates that require direct K1 + TSL binary analysis were **not** added here, because those binaries were not available in the current environment during this work.

## Related pages

- [Indoor Map Builder User Guide](Indoor-Map-Builder-User-Guide)
- [Indoor Map Builder Implementation Guide](Indoor-Map-Builder-Implementation-Guide)
- [BWM File Format](BWM-File-Format)
- [MDL/MDX File Format](MDL-MDX-File-Format)
