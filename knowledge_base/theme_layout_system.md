# GhostRigger Theme and Layout System

GhostRigger themes and layouts are XML files intended for both packaged
defaults and community customization.

## Files

- Theme engine: `src/gui/libtheme/`
- Packaged themes: `config/themes/themes/`
- Packaged layouts: `config/themes/layouts/`
- User themes: platform config directory `GhostRigger/themes/`
- User layouts: platform config directory `GhostRigger/layouts/`

User files load after packaged defaults. If ids collide, the user file wins and
the manager records a diagnostic warning.

## Theme XML

Themes define appearance only: colors, fonts, icon provider defaults, icon
sizes, spacing tokens, button metrics, and contrast mode.

Required root attributes:

```xml
<theme id="matrix" name="Matrix" version="1">
```

Recommended sections:

- `metadata`: author, description, mode, highContrast
- `colors`: named tokens such as `window.background`, `panel.border`,
  `text.primary`, `accent.primary`, `button.background`, `warning`
- `fonts`: role-based fonts such as `default`, `monospace`, `heading`
- `icons`: provider, default button mode, toolbar icon sizes
- `metrics`: toolbar height, button height, spacing, panel metrics, splitter
  handle width

Widgets should consume colors through the application stylesheet first. Custom
painted widgets should expose `apply_ghost_theme(theme)` and read tokens with
`theme.color("token.name")` or `theme.metric("metric.name")`.

## Layout XML

Layouts define structure only: window size, panel widths/heights, splitter
proportions, toolbar visibility, toolbar button mode, and viewport density.

Required root attributes:

```xml
<layout id="default" name="Default" version="1">
```

Known panel ids include `library`, `modules`, `properties`,
`animationLibrary`, `meshTools`, `outputLog`, and `pythonTerminal`. Unknown ids
warn but do not crash, so future panels can be added safely.

Supported button modes:

- `iconOnly`
- `textOnly`
- `iconText`
- `textBesideIcon`
- `textUnderIcon`

Tooltips must always keep the full action name, especially for icon-only
layouts.

## Runtime

`ThemeManager` loads packaged themes, then user themes, resolves manual vs
Follow OS mode through `darkdetect`, persists selected ids, and applies a
generated Qt stylesheet. `LayoutManager` loads packaged/user layouts, persists
the selected layout and overrides, and applies real splitter, panel, viewport,
and toolbar metrics.

Hot reload uses `watchdog` when enabled in Settings. Theme XML changes are
reloaded and reapplied. Layout XML changes are reloaded and the user is asked
before the active UI is rearranged.

## Troubleshooting

Invalid XML should not crash GhostRigger. Use Settings -> Theme/Layout ->
Validate Theme Files or Validate Layout Files. Common issues are missing root
attributes, invalid hex colors, unsupported button modes, and preferred sizes
smaller than minimum sizes.
