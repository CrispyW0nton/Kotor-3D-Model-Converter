# GhostRigger Theme and Layout System

GhostRigger themes and layouts are XML files intended for both packaged
defaults and community customization.

## Module Editor Notes

The standalone Module Editor is theme/layout aware. It consumes the active `ThemeManager` stylesheet and `LayoutManager` metrics, uses the `moduleEditor` toolbar id for its top command strip, and keeps KMAP outliner/properties/validation/export panels on shared table, tree, input, splitter, and toolbar metrics. No new colour tokens are required for the first KMAP pass.

## Files

- Theme engine: `src/gui/libtheme/`
- Packaged themes: `config/themes/themes/`
- Packaged layouts: `config/themes/layouts/`
- User themes: platform config directory `GhostRigger/themes/`
- User layouts: platform config directory `GhostRigger/layouts/`

User files load after packaged defaults. If ids collide, the user file wins and
the manager records a diagnostic warning.

Packaged theme ids are `default`, `matrix`, `droid`, `dark`, `light`, and
`classic`. `default` sets `application.native=true`, which tells the theme
engine to apply no generated GhostRigger stylesheet and restore the Qt platform
palette. `droid` captures the dark graphite startup-console look: grey panels
and controls, bright Matrix-green accents, high-contrast text, and the default
Aurebesh Matrix bar font.

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
- `styles`: application/native mode, tab mode, Matrix bar mode/glyph/font/image

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
generated Qt stylesheet. `ThemeApplier` caches generated stylesheets, coalesces
rapid apply requests, skips unchanged applies, temporarily disables updates on
the target window during bulk apply, and emits `themeChanged` once per
successful full apply. Theme-aware widgets must not call back into
`ThemeManager.apply_current_theme()` from their change handlers.

`LayoutManager` loads packaged/user layouts, persists the selected layout and
overrides, and applies real splitter, panel, viewport, row-height, input-height,
and toolbar metrics.

Hot reload uses `watchdog` when enabled in Settings. Theme XML changes are
reloaded and reapplied. Layout XML changes are reloaded and the user is asked
before the active UI is rearranged.

## Theme Editor

Open **Settings -> Theme/Layout -> Theme Editor...**. The editor separates:

- Theme values: colours, fonts, icon provider/defaults.
- Matrix Bar values: mode, optional glyph alphabet, optional font override,
  optional PNG/GIF path, and crop rectangle.
- Layout values: sizes, density, panel widths, row heights, button mode.

Changing a colour, font, metric, or button mode updates only the editor preview
pane. Use **Apply Theme** or **Apply Layout** to apply the edited values to the
whole application. Use **Save** / **Save Theme As** / **Save Layout As** to
write XML into the user config directory. Existing user XML receives a `.bak`
backup before overwrite.

Packaged XML should not be overwritten for personal customisation. Duplicate a
theme or save as a user override instead.

## Token Coverage

Core colour tokens include:

- `window.background`, `window.text`
- `panel.background`, `panel.backgroundAlt`, `panel.border`,
  `panel.headerBackground`, `panel.headerText`
- `groupbox.border`, `groupbox.title`
- `toolbar.background`, `toolbar.border`
- `button.background`, `button.text`, `button.hover`, `button.pressed`,
  `button.checked`, `button.checkedText`, `button.disabledBackground`,
  `button.disabledText`
- `input.background`, `input.text`, `input.border`, `input.focusBorder`
- `spinbox.buttonBackground`, `spinbox.buttonHover`,
  `spinbox.buttonPressed`, `spinbox.buttonBorder`, `spinbox.arrow`
- `tab.background`, `tab.selectedBackground`, `tab.text`,
  `tab.selectedText`
- `table.background`, `table.text`, `table.headerBackground`,
  `table.headerText`, `table.grid`
- `tree.background`, `tree.text`
- `scrollbar.background`, `scrollbar.handle`
- `selection.background`, `selection.text`
- `viewport.background`, `viewport.gridMajor`, `viewport.gridMinor`,
  `viewport.text`
- `transformBar.background`, `transformBar.border`
- `warning`, `error`, `success`, `info`

Core metric tokens include:

- `window.defaultWidth`, `window.defaultHeight`
- `toolbar.height`, `toolbar.iconSize`, `toolbar.buttonHeight`,
  `toolbar.buttonMinWidth`, `toolbar.spacing`
- `button.height`, `button.minWidth`, `button.paddingX`, `button.paddingY`
- `input.height`, `combo.height`, `spinbox.height`,
  `spinbox.buttonWidth`, `checkbox.spacing`
- `tab.height`, `table.rowHeight`, `tree.rowHeight`
- `panel.margin`, `panel.spacing`, `panel.headerHeight`,
  `panel.minWidth`, `panel.preferredWidth`
- `leftPanel.preferredWidth`, `rightPanel.preferredWidth`,
  `farRightPanel.preferredWidth`, `bottomPanel.preferredHeight`
- `groupbox.margin`, `groupbox.spacing`, `splitter.handleWidth`
- `statusbar.height`, `viewportToolbar.height`, `transformBar.height`

Font roles are `default`, `monospace`, `heading`, `small`, `viewport`, and
`terminal`. The Matrix bar uses the `matrix` font role unless
`matrixBar.fontFamily` is set in the theme styles.

Style tokens include `application.native`, `tab.mode`, `matrixBar.style`,
`matrixBar.glyphs`, `matrixBar.fontFamily`, `matrixBar.imagePath`,
`matrixBar.cropX`, `matrixBar.cropY`, `matrixBar.cropW`, and
`matrixBar.cropH`. Supported `matrixBar.style` values are `matrix`, `png`,
`gif`, and `disabled`; crop values are percentages.

## Fixing Widgets

For ordinary controls, prefer the application stylesheet and remove local
hardcoded stylesheets. For custom-painted widgets, add:

```python
def apply_ghost_theme(self, theme):
    self._background = QtGui.QColor(theme.color("viewport.background"))
    self.update()

def apply_ghost_layout(self, layout):
    self.row_height = layout.spacing_value("tableRowHeight", 22)
    self.updateGeometry()
```

Register standalone windows with the parent `ThemeManager`, or call these hooks
from the parent when the window is constructed. Do not trigger a full theme
apply from inside `apply_ghost_theme`.

## Performance Debugging

Theme applies log stylesheet build time, application stylesheet/palette apply
time, hook/icon refresh time, and total time. Look for repeated apply lines with
the same theme id: that usually means a widget is creating a loop from
`themeChanged`. Expensive fixes should happen in the widget hook, not by
rebuilding the global stylesheet.

Useful checks:

```bash
python tools/validate_themes.py
pytest tests/test_theme_layout_loading.py -q
```

## Troubleshooting

Invalid XML should not crash GhostRigger. Use Settings -> Theme/Layout ->
Validate Theme Files or Validate Layout Files. Common issues are missing root
attributes, invalid hex colors, unsupported button modes, and preferred sizes
smaller than minimum sizes.
