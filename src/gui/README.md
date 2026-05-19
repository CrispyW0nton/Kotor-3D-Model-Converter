# GUI Package Layout

`src/gui` keeps implementation modules in category folders. The package root is
kept intentionally small: `qt_lib.py` is the central GUI facade, and
`__init__.py` keeps `src.gui` importable.

GUI code outside the category folders should import through the stable
`src.gui.qt_lib` facade. For example:

```python
from src.gui.qt_lib.panels.qt_common_panels import QtToolPanel
from src.gui.qt_lib.rendering.viewport_core import FrameRenderer
```

The `src.gui.qt_lib.<category>.<module>` aliases mirror the grouped
implementation folders below. Do not add new root-level `src/gui/*.py` shim
modules.

Implementation files are organized by category:

- `assets/` - theme, icons, and visual background helpers
- `dialogs/` - Qt dialogs and dialog helpers
- `panels/` - reusable Qt panels and dock-style UI sections
- `rendering/` - viewport renderers, rasterizer acceleration, and navigation helpers
- `textures/` - texture atlas and TPC rendering utilities
- `viewports/` - Qt viewport widgets and UV viewer windows
- `windows/` - top-level Qt windows and workbench-style tools
