# PyKotor Design System Rules

Comprehensive design system documentation for integrating Figma designs using Model Context Protocol.

## 1. Design System Structure

### Token Definitions

**Location**: Not centrally defined - tokens are scattered across:
- `Tools/HolocronToolset/src/toolset/gui/` - UI styling
- `Libraries/PyKotor/src/utility/gui/qt/` - Qt widget utilities
- Individual `.qss` stylesheets (if present)

**Format**: Currently no formal token system. Colors, typography, and spacing are hardcoded in Python/Qt code.

**Recommendation**: Implement a centralized token system at:
```
Libraries/PyKotor/src/utility/gui/qt/design_tokens/
├── colors.py
├── typography.py
├── spacing.py
└── __init__.py
```

Example token structure:
```python
# colors.py
class ColorTokens:
    # Primary
    PRIMARY_500 = "#3B82F6"
    PRIMARY_600 = "#2563EB"
    
    # Surface
    SURFACE_DEFAULT = "#FFFFFF"
    SURFACE_ELEVATED = "#F9FAFB"
    
    # Text
    TEXT_PRIMARY = "#111827"
    TEXT_SECONDARY = "#6B7280"
```

### Component Library

**Location**: Custom Qt widgets are defined in:
- `Libraries/PyKotor/src/utility/gui/qt/widgets/` - Core reusable widgets
- `Tools/HolocronToolset/src/toolset/gui/widgets/` - Toolset-specific widgets
- `Tools/HolocronToolset/src/toolset/gui/common/widgets/` - Common toolset widgets

**Component Architecture**:
```
QWidget (Qt Base)
├── Custom Base Widgets
│   ├── LongSpinBox - 64-bit integer input
│   ├── ComboBox2DA - 2DA data selection
│   ├── ColorEdit - RGB/RGBA color picker
│   └── LocStringEdit - Localized string editor
├── Complex Widgets
│   ├── CommandPalette - VS Code-style command palette
│   ├── CollapsibleWidget - Expandable sections
│   ├── BreadcrumbsWidget - Navigation breadcrumbs
│   └── CodeEditor - Syntax highlighting editor
└── Editor Windows
    ├── Editor (Base) - Generic resource editor
    ├── DLGEditor - Dialog tree editor
    ├── UTCEditor - Creature editor
    └── [13+ other resource editors]
```

**Example Component**:
```python
# Libraries/PyKotor/src/utility/gui/qt/widgets/edit/spinbox.py
class LongSpinBox(QAbstractSpinBox):
    """Custom spinbox for 64-bit integers."""
    valueChanged = Signal(int)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._value = 0
        self._minimum = -(2**63)
        self._maximum = 2**63 - 1
```

**Documentation**: No formal storybook. Components documented via docstrings.

## 2. Frameworks & Libraries

### UI Framework
- **Primary**: QtPy (abstraction layer)
- **Backend**: PyQt6 (preferred), with PyQt5/PySide2/PySide6 support
- **Version**: PyQt6 >= 6.0

### Styling Libraries
- **Qt Stylesheets (QSS)**: Used for theming
- **Custom Painting**: QPainter for complex rendering
- **No CSS frameworks**: Pure Qt/Python approach

### Build System
- **Package Manager**: UV (modern Python package manager)
- **Bundler**: PyInstaller (primary), Nuitka (experimental)
- **Task Runner**: VS Code tasks + PowerShell scripts
- **Testing**: pytest with pytest-qt

## 3. Asset Management

### Storage Structure
```
Tools/HolocronToolset/src/toolset/
├── help/images/ - Help documentation images
├── rcc/ - Qt Resource Collection files
└── resources_rc_pyqt6.py - Compiled resources
```

### Asset References
```python
# Via Qt Resource System
pixmap = QPixmap(":/images/icons/sith.png")

# Direct file path
image = QImage("toolset/help/images/screenshot.png")
```

### Asset Optimization
- **Images**: No automatic optimization
- **Icons**: SVG preferred, PNG fallback
- **Bundling**: PyInstaller includes all assets in executable

### CDN
No CDN - all assets bundled with application.

## 4. Icon System

### Storage Location
```
Tools/HolocronToolset/src/toolset/resources/
Tools/HolocronToolset/src/toolset/help/images/icons/
```

### Icon Usage
```python
from qtpy.QtGui import QIcon, QPixmap

# Load icon
icon = QIcon(":/images/icons/folder.png")
button.setIcon(icon)

# Set window icon
self.setWindowIcon(QIcon(":/images/icons/sith.png"))
```

### Icon Naming Convention
- Lowercase with underscores: `folder_open.png`
- Descriptive names: `save_icon.png`, `delete_icon.png`
- No formal icon library system

### Recommendation
Implement icon library:
```python
# utility/gui/qt/icons.py
class Icons:
    FOLDER = QIcon(":/icons/folder.svg")
    FILE = QIcon(":/icons/file.svg")
    SAVE = QIcon(":/icons/save.svg")
    # etc.
```

## 5. Styling Approach

### CSS Methodology
**Qt Stylesheets (QSS)** - Qt's CSS-like syntax:

```python
# Example QSS
stylesheet = """
QWidget {
    background-color: #2D2D30;
    color: #F0F0F0;
}

QPushButton {
    background-color: #0E639C;
    border: 1px solid #007ACC;
    padding: 5px 15px;
    border-radius: 3px;
}

QPushButton:hover {
    background-color: #1177BB;
}
"""
widget.setStyleSheet(stylesheet)
```

### Global Styles
- **Location**: Applied per-widget or per-window
- **Theming**: Dark/Light theme support via stylesheet switching
- **No global CSS file**: Styles applied programmatically

### Responsive Design
- **Layout Managers**: QVBoxLayout, QHBoxLayout, QGridLayout
- **Size Policies**: QSizePolicy for flexible sizing
- **No media queries**: Qt's layout system handles responsiveness

```python
# Responsive layout example
layout = QVBoxLayout()
layout.setStretch(0, 1)  # Widget 0 takes 1 part
layout.setStretch(1, 3)  # Widget 1 takes 3 parts
```

## 6. Project Structure

### Overall Organization
```
PyKotor/
├── Libraries/
│   └── PyKotor/ - Core library
│       ├── src/
│       │   ├── pykotor/ - Game resource handlers
│       │   └── utility/ - Utility libraries
│       └── tests/
├── Tools/
│   ├── BatchPatcher/ - Batch processing tool
│   ├── HolocronToolset/ - Main GUI editor suite
│   │   ├── src/toolset/
│   │   │   ├── gui/ - UI components
│   │   │   │   ├── editors/ - Resource editors
│   │   │   │   ├── widgets/ - Custom widgets
│   │   │   │   ├── windows/ - Main windows
│   │   │   │   └── common/ - Shared UI code
│   │   │   ├── uic/ - Generated UI code
│   │   │   │   └── qtpy/ - Qt UI classes
│   │   │   ├── data/ - Data files
│   │   │   └── utils/ - Utilities
│   │   └── tests/
│   ├── HoloPatcher/ - Mod installer
│   ├── HoloPazaak/ - Pazaak game
│   └── KotorDiff/ - Diff tool
├── compile/ - Build scripts
├── docs/ - Documentation
├── tests/ - Integration tests
└── pyproject.toml - Workspace config
```

### Feature Organization Pattern
**Editor Pattern**:
```
toolset/gui/editors/<resource_type>/
├── editor.py - Main editor class
├── model.py - Data model
├── list_widget_base.py - List widgets
├── tree_view.py - Tree views
├── widget_windows.py - Helper windows
└── settings.py - Editor settings
```

**Example**:
```
toolset/gui/editors/dlg/
├── editor.py - DLGEditor class
├── model.py - DLGStandardItemModel
├── list_widget_base.py - DLGListWidget
├── tree_view.py - DLGTreeView
└── settings.py - DLGSettings
```

## 7. UI Code Generation

### From .ui Files
Qt Designer creates `.ui` XML files, converted to Python:

```powershell
# Convert .ui to Python
pyuic6 -o output.py input.ui
```

**Generated Files Location**:
```
Tools/HolocronToolset/src/toolset/uic/qtpy/
├── editors/
│   ├── dlg.py - DLG editor UI
│   ├── utc.py - UTC editor UI
│   └── [other editors]
└── dialogs/
    ├── about.py - About dialog UI
    ├── property.py - Property editor UI
    └── [other dialogs]
```

### Usage Pattern
```python
from toolset.uic.qtpy.editors.dlg import Ui_MainWindow

class DLGEditor(Editor):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.ui = Ui_MainWindow()
        self.ui.setupUi(self)
        # Connect signals, customize...
```

## 8. Figma Integration Strategy

### Recommended Workflow

1. **Design in Figma**
   - Create UI designs in Figma
   - Use proper component naming
   - Organize with frames/sections

2. **Generate UI Code**
   - Use Figma → Qt Designer export (if available)
   - Or manually recreate in Qt Designer
   - Save as `.ui` files

3. **Convert to Python**
   - Run `pyuic6` to generate Python UI classes
   - Place in `toolset/uic/qtpy/` directory

4. **Implement Logic**
   - Create editor class
   - Import generated UI class
   - Connect signals/slots
   - Add business logic

5. **Apply Styling**
   - Extract colors/typography from Figma
   - Create QSS stylesheet
   - Apply to widgets

### Code Connect Mapping Example

```python
# For a Figma component "ButtonPrimary"
# Map to: Libraries/PyKotor/src/utility/gui/qt/widgets/button.py

from qtpy.QtWidgets import QPushButton

class PrimaryButton(QPushButton):
    """Primary action button matching Figma design."""
    def __init__(self, text="", parent=None):
        super().__init__(text, parent)
        self.setStyleSheet("""
            QPushButton {
                background-color: #0E639C;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
                font-size: 14px;
                font-weight: 500;
            }
            QPushButton:hover {
                background-color: #1177BB;
            }
            QPushButton:pressed {
                background-color: #0D5A8F;
            }
        """)
```

## 9. Key Design Patterns

### Editor Pattern
All resource editors follow this structure:

```python
class ResourceEditor(Editor):
    def __init__(self, parent, installation):
        super().__init__(parent, "Editor Name", "icon", 
                        supported_types, installation)
        self.ui = Ui_MainWindow()
        self.ui.setupUi(self)
        self._setupSignals()
    
    def _setupSignals(self):
        """Connect UI signals to handlers."""
        pass
    
    def load(self, filepath, resref, restype, data):
        """Load resource into editor."""
        pass
    
    def build(self):
        """Build resource from UI state."""
        pass
```

### Dialog Pattern
```python
class CustomDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        from toolset.uic.qtpy.dialogs.custom import Ui_Dialog
        self.ui = Ui_Dialog()
        self.ui.setupUi(self)
        self._setup_event_filter()
    
    def _setup_event_filter(self):
        """Prevent scroll wheel on spinboxes/comboboxes."""
        self._no_scroll_filter = NoScrollEventFilter(self)
        self._no_scroll_filter.setup_filter(self)
```

### Widget Pattern
```python
class CustomWidget(QWidget):
    valueChanged = Signal(object)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()
        self._connect_signals()
    
    def _setup_ui(self):
        """Create and layout child widgets."""
        pass
    
    def value(self):
        """Get current value."""
        pass
    
    def setValue(self, value):
        """Set value and emit signal."""
        pass
```

## 10. Color Palette Extraction

### Current Colors (from code analysis)
```python
# Dark Theme Colors
BACKGROUND_PRIMARY = "#2D2D30"
BACKGROUND_SECONDARY = "#252526"
SURFACE = "#3E3E42"
BORDER = "#3F3F46"

# Text Colors
TEXT_PRIMARY = "#CCCCCC"
TEXT_SECONDARY = "#808080"
TEXT_DISABLED = "#656565"

# Accent Colors
ACCENT_BLUE = "#007ACC"
ACCENT_BLUE_HOVER = "#1177BB"
ACCENT_BLUE_PRESSED = "#0D5A8F"

# Status Colors
SUCCESS = "#89D185"
WARNING = "#DDB100"
ERROR = "#F48771"
INFO = "#75BEFF"
```

## 11. Typography System

### Font Stack
```python
# Default Qt fonts
DEFAULT_FONT = QFont("Segoe UI", 9)  # Windows
# "SF Pro Text" on macOS
# "Ubuntu" on Linux

# Code Editor
CODE_FONT = QFont("Consolas", 10)  # Monospace
```

### Type Scale
```python
# Sizes (in points)
FONT_XS = 8
FONT_SM = 9
FONT_BASE = 10
FONT_LG = 11
FONT_XL = 12
FONT_2XL = 14
FONT_3XL = 16
```

## 12. Spacing System

### Layout Spacing
```python
# Standard margins/padding (in pixels)
SPACING_XS = 2
SPACING_SM = 4
SPACING_MD = 8
SPACING_LG = 16
SPACING_XL = 24
SPACING_2XL = 32
```

### Usage
```python
layout.setContentsMargins(
    SPACING_LG,  # left
    SPACING_LG,  # top
    SPACING_LG,  # right
    SPACING_LG   # bottom
)
layout.setSpacing(SPACING_MD)
```

## 13. FigJam Diagram Integration

All architectural diagrams are documented in [FIGMA_DIAGRAMS.md](../../FIGMA_DIAGRAMS.md).

### Using Diagrams in Code Comments
```python
# Architecture: See FIGMA_DIAGRAMS.md - "DLG Editor Node Management"
# Diagram ID: e53d6e87-5d53-4135-9782-9a6d1428b5f8

class DLGEditor(Editor):
    """Dialog editor implementing the node management workflow.
    
    Flow: Load DLG → Tree View → Select Node → Edit Properties → Save
    See architectural diagram for complete sequence.
    """
```

## 14. Best Practices

### Qt Best Practices
1. **Use layouts, not fixed positions**: Responsive design
2. **Signal/slot connections**: Decouple UI from logic
3. **QStyle for native look**: Platform-appropriate styling
4. **Resource system**: Embed assets in binary
5. **Event filters**: Non-invasive behavior modification

### Python Best Practices
1. **Type hints**: Full type coverage
2. **Docstrings**: Google style
3. **F-strings**: Modern string formatting
4. **Context managers**: Resource management
5. **Dataclasses**: Structured data

### Toolset-Specific
1. **HTInstallation**: Always pass installation reference
2. **ResourceType**: Use enum, not strings
3. **Editor base class**: Inherit for consistency
4. **NoScrollEventFilter**: Apply to dialogs with spinboxes
5. **Undo/Redo**: Use QUndoStack for editor actions

---

## Summary

The PyKotor project uses **QtPy/PyQt6** for UI with a **custom widget library** built on top of Qt. There's no formal design token system yet, but one is recommended. Integration with Figma should follow the **Design → Qt Designer → PyUIC → Python** workflow, with manual styling via QSS to match Figma designs.

For any new components, create reusable widgets in `utility/gui/qt/widgets/` and document them with docstrings and type hints. Reference the comprehensive FigJam diagrams in `FIGMA_DIAGRAMS.md` for architectural guidance.
