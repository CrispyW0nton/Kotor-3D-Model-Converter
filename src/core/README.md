# GhostRigger Core Backend

## Purpose

`src/core` contains GhostRigger's backend systems: model data, game-resource loading, MDL IO, module handling, scene services, validation, workflows, and export bridges. The package is organised by subsystem so backend code can grow without returning to a flat folder of unrelated modules. The root of `src/core` should stay as small as the root of `src/gui`: package folders plus `__init__.py`, `qt_core.py`, and this README.

## Folder Structure

- `animation/` - animation playback, animation libraries, supermodel helpers, and GPU skinning support.
- `animation_retargeting/` - KotOR-to-KotOR retargeting and skeleton template selection.
- `assets/` - asset preview, resource manager, and override layer services.
- `characters/` - character builder, creature appearance, and body/head workflows.
- `diagnostics/` - diagnostics, validation, and module reference safety checks.
- `export/` - glTF and Unity import/export bridges.
- `game/` - KotOR installation, game loading, and PyKotor integration helpers.
- `geometry/` - model data structures, vertex-space helpers, and map snapping tools.
- `lighting/` - particle and effect helpers.
- `mdl/` - MDL readers, parsers, writers, wrappers, and porting helpers.
- `modules/` - module loading, formats, hydration, inspection, packaging, and save pipelines.
- `scene/` - scene graph, room graph, and VIS editing services.
- `skeleton/` - skeleton construction helpers.
- `templates/` - template builders and 2DA helpers.
- `walkmesh/` - walkmesh editing and rendering helpers.
- `workflow/` - shared workflow base classes and composite workflows.
- `special/` - specialised integration, compatibility, and legacy helpers.

## Central Import Hub

`src/core/qt_core.py` is the central backend facade and grouped import hub for common public APIs used by Qt-facing code and tools. It mirrors `src/gui/qt_lib.py`: implementation modules live in subsystem folders, while `qt_core.py` exposes lazy grouped routes such as `src.core.qt_core.modules.module_loader`.

It should not contain business logic, file-format logic, GUI widget logic, or broad wildcard imports from implementation modules.

Example:

```python
from src.core.qt_core import SceneManager, ModuleLoader, ResourceManager
```

Use the grouped routes when a caller needs a specialised API that is not part of the curated facade:

```python
from src.core.qt_core.modules.module_format import ModuleData
```

## Subsystems

Each subsystem package owns a coherent backend area. Keep domain logic in core packages and keep GUI modules as consumers of backend services. GUI code should not directly own parsing, loading, validation, save-pipeline, or export logic. Core code should avoid hard dependencies on Qt widgets or other GUI objects.

## Compatibility Shims

There are no flat compatibility shim files in the root of `src/core`. The root is intentionally not a compatibility dumping ground. Keep it limited to:

```text
src/core/
    __init__.py
    qt_core.py
    README.md
    <subsystem folders>/
```

Old flat imports such as:

```python
from src.core.scene_manager import SceneManager
from src.core.module_loader import ModuleLoader
from src.core.mdl_parser import MDLAsciiParser
```

should be migrated to `src.core.qt_core`:

```python
from src.core.qt_core import SceneManager, ModuleLoader, MDLAsciiParser
```

or to a grouped route:

```python
from src.core.qt_core.scene.scene_manager import SceneManager
from src.core.qt_core.modules.module_loader import ModuleLoader
from src.core.qt_core.mdl.mdl_parser import MDLAsciiParser
```

## Rules for Adding New Core Modules

Do not dump new feature files directly into `src/core`. Create or reuse a subsystem package. If a feature is large, split it into small backend roles such as models, controllers, services, serializers, adapters, and validators.

Bad:

```text
src/core/new_big_feature.py
```

Good:

```text
src/core/new_big_feature/
    __init__.py
    feature_model.py
    feature_controller.py
    feature_service.py
    feature_serializer.py
```

## Import Style Guide

GUI and tool consumers should prefer the facade for common backend services:

```python
from src.core.qt_core import KotorModel, SceneManager, ValidationService
```

For specialised APIs outside the facade, GUI and tool consumers should use grouped `qt_core` routes:

```python
from src.core.qt_core.assets.resource_manager import RES_TPC
from src.core.qt_core.animation.gpu_skinning import MatrixPaletteUploader
```

Core subsystem modules should prefer explicit relative imports to other subsystem modules:

```python
from ..geometry.model_data import KotorModel
from ..diagnostics.validation_service import ValidationService
```

Avoid wildcard imports in implementation modules. Avoid `sys.path` manipulation. Do not add new flat Python files directly under `src/core`. If a dependency would create a circular import, use a narrow local import inside the function that needs it.

## Future Expansion Notes

New backend systems should keep GUI concerns at the edges and should expose stable APIs through `qt_core.py` only when they become common cross-subsystem dependencies. If a subsystem grows large, split it into model, controller, service, serializer, adapter, and validator modules inside that subsystem instead of adding root-level files.
