# GhostRigger Themes and Layouts

Packaged themes live in `config/themes/themes/`. Packaged layouts live in
`config/themes/layouts/`. These files are normal XML and are intended to be
readable by modders.

Built-in themes are:

- `default.xml`: platform/native Qt styling; no generated GhostRigger QSS.
- `matrix.xml`: high-contrast GhostRigger Matrix green.
- `droid.xml`: dark graphite droid console, grey controls, Matrix-green accents.
- `dark.xml`: quieter professional dark UI.
- `light.xml`: modern light UI.
- `classic.xml`: traditional light DCC/tool UI.

Themes define colours, fonts, icon provider defaults, Matrix bar style, and visual tokens.
Layouts define window size, panel widths, splitter proportions, toolbar
visibility, row heights, control density, and button display modes.
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
