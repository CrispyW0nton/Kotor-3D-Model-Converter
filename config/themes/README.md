# GhostRigger Themes and Layouts

Packaged themes live in `config/themes/themes/`. Packaged layouts live in
`config/themes/layouts/`. These files are normal XML and are intended to be
readable by modders.

Themes define colours, fonts, icon provider defaults, and sizing tokens.
Layouts define window size, panel widths, splitter proportions, toolbar
visibility, and button display modes.

User themes and layouts can be placed in the platform-specific GhostRigger
config directory:

- `GhostRigger/themes/`
- `GhostRigger/layouts/`

If a user file uses the same id as a packaged file, GhostRigger treats it as an
intentional override and reports that in diagnostics. Invalid XML is ignored
with a warning; the current theme/layout remains active.

Safe editing tips:

- Keep `id`, `name`, and `version` on the root element.
- Use six-digit hex colours such as `#00FF7A`.
- Use supported button modes: `iconOnly`, `textOnly`, `iconText`,
  `textBesideIcon`, `textUnderIcon`.
- Change packaged files only when updating the application defaults. Put
  personal/community variants in the user config directory.
