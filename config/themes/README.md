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
The Theme Editor owns Matrix bar appearance. Its Matrix Bar tab writes
`matrixBar.style`, `matrixBar.glyphs`, `matrixBar.fontFamily`, and
`matrixBar.imagePath` into the theme `<styles>` section, along with
`matrixBar.cropX`, `matrixBar.cropY`, `matrixBar.cropW`, and
`matrixBar.cropH` for selecting the image region. Matrix bar colours remain
editable as `matrixBar.*` colour tokens.
The Theme Editor also owns startup splash branding. Its Splash tab writes
`splash.logoPath`, `splash.productText`, `splash.subtitleText`, and
`splash.copyrightText` into `<styles>`, plus `splash.surfaceStyle` for the
surface finish (`matte`, `bevelled`, `glossy`, or `flat`), and writes
`splash.width`, `splash.height`, and `splash.logoSize` into `<metrics>`. The
splash itself uses `splash.background`, `splash.panel`, `splash.brandBackground`,
`splash.progressBackground`, `splash.border`, `splash.text`,
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
