# GUI Package Layout

`src/gui` keeps implementation modules in category folders. The package root is
kept intentionally small: `qt_lib.py` is the central GUI facade, and
`__init__.py` keeps `src.gui` importable.

GUI code outside the category folders should import through the stable
`src.gui.qt_lib` facade. For example:

```python
from src.gui.qt_lib.panels.qt_common_panels import QtToolPanel
from src.gui.rendering.frame_core.renderer import FrameRenderer
```

The `src.gui.qt_lib.<category>.<module>` aliases mirror the grouped
implementation folders below. Do not add new root-level `src/gui/*.py` shim
modules.

Implementation files are organized by category:

- `assets/` - theme, icons, and visual background helpers
- `camera/` - camera models, controllers, overlays, and ArcBall camera state
- `dialogs/` - Qt dialogs and dialog helpers
- `panels/` - reusable Qt panels and dock-style UI sections
- `rendering/` - renderer backends, software frame rendering, rasterizer acceleration, and GPU-facing helpers
- `textures/` - texture atlas, TPC/TXI parsing, and texture rendering utilities
- `viewports/` - Qt viewport widgets, frame display state, navigation profiles, and thin viewport facades
- `windows/` - top-level Qt windows and workbench-style tools

Shared math helper modules are not owned by GUI categories. Add or consume them
through `src/math/` and keep GUI-side math files as compatibility shims only.
