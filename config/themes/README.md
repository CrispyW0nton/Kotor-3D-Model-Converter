# GhostRigger Themes and Layouts

Packaged themes live in `config/themes/themes/`. Packaged layouts live in
`config/themes/layouts/`. These files are normal XML and are intended to be
readable by modders.

Built-in themes are:

- `default.xml`: platform/native Qt styling; no generated GhostRigger QSS.
- `default_matrix.xml`: Default/native widget geometry with Matrix colours.
- `default_droid.xml`: Default/native widget geometry with Droid colours.
- `default_dark.xml`: Default/native widget geometry with Dark colours.
- `default_light.xml`: Default/native widget geometry with Light colours.
- `default_classic.xml`: Default/native widget geometry with Classic colours.

The Default/native theme uses neutral native-style colour tokens, not Matrix
fallback colours. `ThemeLoader` also repairs stale Matrix fallback values when
older user overrides of a native theme are loaded.
The `default_*` themes are palette-only variants: they keep the same native
widget structure and layout behaviour as Default, skip generated QSS, and apply
theme colours through the Qt palette plus GhostRigger's custom widget hooks.
Use these as the stable packaged colour themes. The older Matrix/Droid/Dark/
Light/Classic generated-QSS packaged themes have been removed.

Themes define colours, fonts, icon provider defaults, Matrix bar style, and visual tokens.
Layouts define window size, panel widths, splitter proportions, toolbar
visibility, row heights, control density, button display modes, and optional
`<dockLayout>` groups that tab or split dock widgets into workspace profiles.
The unified Content Browser uses the stable `contentBrowser` panel layout id.
The Scene outliner uses `scene`, and Properties uses `properties`; all three
are top-level dock widgets so layouts can size them without squeezing the
viewport through permanent side tabs.
Visual profile layouts are packaged as normal layout XML files:
`profile_animation`, `profile_mesh_editing`, `profile_lighting`,
`profile_cinegraphics`, and `profile_clean`. They are available from the
toolbar Visual Profile dropdown and the Settings layout selector. Dock group
entries use the runtime dock keys `content_browser`, `scene`, `properties`,
`animations`, `nodes`, `lighting`, `cameras`, `module_meshes`, `mesh_tools`,
`sprite_materials`, `adjust_pivot`, `2das`, and `resources`.
`sprite_materials` maps to the stable `spriteMaterials` layout panel id and
owns alpha-card/sprite material display controls for cutout, blended, additive,
window/foliage/fur, and lightsaber-style meshes.
The older `library` and `animationLibrary` ids remain in packaged layouts for
user layout compatibility, but new Library and Animation Library entry points
route through `contentBrowser`.
Custom themes should define the `spinbox.*` colour tokens for numeric
up/down controls: `spinbox.buttonBackground`, `spinbox.buttonHover`,
`spinbox.buttonPressed`, `spinbox.buttonBorder`, and `spinbox.arrow`.
These keep themed `QSpinBox` and `QDoubleSpinBox` steppers as legible as the
native Default theme.
Transform-style numeric controls can also consume `axis.x`, `axis.y`,
`axis.z`, and `axis.text` for compact X/Y/Z badges and axis-coded spin boxes.
The Camera toolbox uses these tokens for position, rotation, and target rows.
The Theme Editor owns Matrix bar appearance. Its Matrix Bar tab writes
`matrixBar.style`, `matrixBar.glyphs`, `matrixBar.fontFamily`, and
`matrixBar.imagePath` into the theme `<styles>` section, along with
`matrixBar.cropX`, `matrixBar.cropY`, `matrixBar.cropW`, and
`matrixBar.cropH` for selecting the image region. Matrix bar colours remain
editable as `matrixBar.*` colour tokens.
The Theme Editor also owns startup splash branding. Its Splash tab writes
`splash.logoPath`, `splash.productText`, `splash.subtitleText`,
`splash.copyrightText`, `splash.useNativePalette`, and
`splash.useBrandedPalette` into `<styles>`, plus
`splash.surfaceStyle` for the
surface finish (`matte`, `bevelled`, `glossy`, or `flat`), and writes
`splash.width`, `splash.height`, and `splash.logoSize` into `<metrics>`. The
splash itself uses `splash.background`, `splash.panel`, `splash.brandBackground`,
`splash.progressBackground`, `splash.logBackground`, `splash.border`, `splash.text`,
`splash.secondaryText`, `splash.accent`, `splash.progressTrack`, and
`splash.progressFill` colour tokens, which the Splash tab exposes next to the
branding controls. Native/default themes are previewed against the live
`QApplication` palette, so the splash matches the actual platform greys even
when the XML file contains portable fallback colours.

User themes and layouts can be placed in the platform-specific GhostRigger
config directory:

- `GhostRigger/themes/`
- `GhostRigger/layouts/`

If a user file uses the same id as a packaged file, GhostRigger treats it as an
intentional override and reports that in diagnostics. Invalid XML is ignored
with a warning; the current theme/layout remains active.

Packaged files are application defaults. Edit them only when changing the
project defaults. Personal and community variants should be saved through the
Theme Editor, which writes to the user config directory and creates `.bak`
backups before overwriting an existing user XML file.

Safe editing tips:

- Keep `id`, `name`, and `version` on the root element.
- Use six-digit hex colours such as `#00FF7A`.
- Use supported button modes: `iconOnly`, `textOnly`, `iconText`,
  `textBesideIcon`, `textUnderIcon`.
- Change packaged files only when updating the application defaults. Put
  personal/community variants in the user config directory.
- Use **Apply Theme** or **Apply Layout** for full-application changes. Theme
  Editor previews are local until explicitly applied.
- Run `python tools/validate_themes.py` after editing packaged defaults.

Layout `<spacing>` may tune menus with `menuBarHeight`,
`menuMinimumWidth`, `menuHorizontalPadding`, `menuShortcutGap`,
`menuIndicatorWidth`, and `menuSubmenuArrowWidth`. GhostStudio combines these
with the active font metrics so long action labels, check/icon columns,
shortcuts, and submenu arrows remain fully visible instead of being clipped.
`responsiveCollapseWidth` sets the logical-pixel width below which secondary
side and bottom docks start hidden; users can reopen them from **Window**.
`windowScreenMargin` optionally reserves logical pixels around an unmaximized
window. Runtime layout application always clamps the requested window size to
the current screen work area, which keeps saved desktop layouts usable on
high-DPI laptops.

Packaged layouts keep ordinary interactive targets at least 24x24 logical
pixels and frequent viewport targets at least 32x32. Theme text pairs must meet
WCAG contrast (4.5:1 for normal text and 3:1 for focus boundaries). Run
**Help > Diagnostics > Accessibility Audit** to inspect the live shell for
missing assistive names, missing icon tooltips, keyboard focus gaps, undersized
targets, duplicate shortcuts, and contrast failures.

Viewport command bars use `viewportToolbar.background` and
`viewportToolbar.border` so the Theme Editor can style their framed surface
separately from general application toolbars.

Viewport selection uses `viewport.selection` for the shared WGPU/ModernGL-style
yellow selected-object edge/helper accent. Viewport helpers use
`viewport.helper.meshHover`, `viewport.helper.light`,
`viewport.helper.lightSelected`, `viewport.helper.camera`,
`viewport.helper.cameraSelected`, `viewport.helper.null`, and
`viewport.helper.nullSelected` so mesh hover, light, camera, and NULL helper
overlays can stay readable in both dark and light themes.

## Module Editor

The standalone Module Editor uses existing theme tokens and layout metrics rather than adding a separate palette. It exposes a `moduleEditor` toolbar layout id for density/button sizing and keeps panels compatible with Default, Matrix, Droid, Dark, Light, Classic plus Default, Compact, Wide, and Cinematic layouts.

Map Studio's horizontal editor splitter allows either authoring rail to
collapse completely. **View > Maximize Viewport** (`Ctrl+Space`) temporarily
hides both rails, the top authoring strips, and lower docks, then restores the
previous arrangement when toggled again.

## GUI Editor

The standalone GUI Editor inherits the active application palette and uses the
stable `guiEditorCatalog` and `guiEditorInspector` panel layout ids for its
retail-resource browser and typed selection inspector. Its texture-backed,
direct-manipulation canvas is custom painted through the active Qt palette; it
introduces no private colour tokens. Add/delete controls, drag/resize handles,
validation, and file commands remain inside the standalone workbench. The
main-workbench GUI Editor command is separate from Map Studio, and PIE consumes
only the renderer-neutral preview payload.

## Custom Rigged Character Builder

The standalone Custom Rigged Character Builder registers as
`customRiggedCharacterBuilder`. It uses the active Qt palette, existing
viewport/theme services, and existing layout metrics; it introduces no private
Matrix-only colors or fixed splitter contract. Its import, rig, ground,
animation, material, gameplay, validation, and install pages must remain
readable in Default/native, Matrix, Droid, Dark, Light, and Classic themes.

## Custom KOTOR Head Builder

The Character Builder selector exposes the Custom KOTOR Head entry through the
stable card layout id `characterBuilderMode.native_kotor_head`. The entry reuses
the existing themed Character Builder window, viewport, rail, inspector, and
layout metrics in Head mode; it introduces no private colors, splitter sizes,
or button modes.

The patch-required Facial Performance Head entry uses the stable card layout id
`characterBuilderMode.facial_performance_head`. Its warning, synchronized
dialogue audio/LIP controls, and playback status use the normal palette,
group-box, form, input, and button roles. No facial-workflow colour token or
fixed panel dimension is introduced.

The vanilla component recipe is part of the existing
`headBuilderProperties` surface. Its carrier, face, eyes, eyelids/lashes, hair,
alien-family, and build controls use ordinary themed forms, grids, labels, and
buttons. They add no private colour tokens or fixed panel dimensions.

## Scripting Suite

The standalone Scripting Suite registers as
`scriptingDialogueStudio`. It inherits the active application palette and uses
existing `main`, `library`, and `output_log` layout metrics for toolbar density,
resource-browser width, editor space, and diagnostics height. No scripting-only
colour tokens are required. Its left navigation composes all twelve preserved
authoring, data, project, package, tutorial, blueprint, and integration pages in
the same workbench. Community layouts can therefore resize the suite without
introducing a second theme or crowding the main viewport.
