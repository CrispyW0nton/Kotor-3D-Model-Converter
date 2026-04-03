# Qt theme package – host-app integration

This package provides a reusable Qt theme manager, catalog, and selector dialog. The **host application** owns settings and persistence; the library only applies theme/style when given names.

## Theme source discovery

Discovery is configurable via `ThemeSources`:

- **`qrc_prefixes`** – Qt resource prefixes scanned for QSS themes (default: `(":/themes",)`). Works with the app’s `.qrc`; if the prefix is missing or empty, built-in themes are still available.
- **`extra_theme_dirs`** – Filesystem paths scanned for VS Code-style JSON theme files. Use for pip-installed or project-specific theme dirs.

Example for an app that adds a filesystem theme directory:

```python
from utility.gui.qt.widgets.theme import ThemeManager, ThemeSources

sources = ThemeSources().with_extra_dirs("/path/to/extra_themes")
manager = ThemeManager(theme_sources=sources)
```

Default `ThemeManager()` uses `ThemeSources()` (qrc `:/themes` only); built-in catalog themes are always included even when no QRC is present.

## Host-app integration pattern

1. **Create manager** (optional: pass `theme_sources` and/or `on_theme_error`).
2. **Apply on startup** using persisted theme/style from your settings.
3. **Open selector dialog** with optional `tr` and `theme_manager`; connect `theme_changed` and `style_changed` to your handlers.
4. **Persist in signal handlers**: update your settings and call `manager.apply_theme_and_style(theme_name, style_name)` (or use wrapper methods that do the apply).

Example:

```python
# At startup
manager = ThemeManager(theme_sources=my_sources)
manager.apply_theme_and_style(
    my_settings.selected_theme or "sourcegraph-dark",
    my_settings.selected_style or "Fusion",
    fallback_theme="sourcegraph-dark",
    fallback_style="Fusion",
)

# When opening the selector
from utility.gui.qt.widgets.theme import ThemeSelectorDialog

dialog = ThemeSelectorDialog(
    parent=self,
    theme_manager=manager,
    available_themes=list(manager.get_available_themes()),
    available_styles=list(manager.get_default_styles()),
    current_theme=my_settings.selected_theme,
    current_style=my_settings.selected_style,
    tr=my_translate_function,
)
dialog.theme_changed.connect(lambda t: (save_theme(t), manager.apply_theme_and_style(t, current_style, ...)))
dialog.style_changed.connect(lambda s: (save_style(s), manager.apply_theme_and_style(current_theme, s, ...)))
dialog.show()
```

## Public API (PyPI-ready)

Import from `utility.gui.qt.widgets.theme`:

- `ThemeManager`, `ThemeDialog`, `ThemeSelectorDialog`
- `ThemeSources`, `ThemeConfig`, `build_builtin_theme_configs`
- `apply_style`, `get_original_style`, `apply_tooltip_style_to_app`, `get_tooltip_stylesheet`
