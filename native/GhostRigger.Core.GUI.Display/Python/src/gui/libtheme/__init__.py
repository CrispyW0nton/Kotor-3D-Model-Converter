"""Professional XML-driven theme and layout support for GhostRigger."""

from pkgutil import extend_path

from .accessibility_audit import (
    AccessibilityAuditor,
    AccessibilityIssue,
    AccessibilityReport,
    audit_theme_contrast,
    contrast_ratio,
    install_accessibility_defaults,
)
from .layout_manager import LayoutManager
from .layout_model import LayoutDefinition, PanelLayout, ToolbarLayout, ViewportLayout
from .os_theme_detector import OSThemeDetector
from .theme_aware import (
    LayoutAwareMixin,
    ThemeAwareMixin,
    ThemedDialog,
    ThemedMainWindow,
    ThemedWidget,
)
from .theme_editor_window import ThemeEditorWindow
from .theme_manager import ThemeManager
from .theme_model import Theme, ThemeFont, ThemeIcons

__path__ = extend_path(__path__, __name__)

__all__ = [
    "AccessibilityAuditor",
    "AccessibilityIssue",
    "AccessibilityReport",
    "LayoutDefinition",
    "LayoutManager",
    "OSThemeDetector",
    "PanelLayout",
    "Theme",
    "ThemeFont",
    "ThemeIcons",
    "ThemeManager",
    "ThemeEditorWindow",
    "LayoutAwareMixin",
    "ThemeAwareMixin",
    "ThemedDialog",
    "ThemedMainWindow",
    "ThemedWidget",
    "ToolbarLayout",
    "ViewportLayout",
    "audit_theme_contrast",
    "contrast_ratio",
    "install_accessibility_defaults",
]
