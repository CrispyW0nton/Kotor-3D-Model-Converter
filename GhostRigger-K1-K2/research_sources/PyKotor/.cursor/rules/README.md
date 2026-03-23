# Cursor Rules - Design System

This directory contains comprehensive rules and guidelines for the PyKotor project's design system, specifically tailored for AI-assisted development with Figma integration.

## Files in This Directory

### design_system_rules.md
Complete design system documentation including:
- Token definitions (colors, typography, spacing)
- Component library structure and patterns
- Qt/PyQt6 framework usage
- Asset management strategies
- Icon system organization
- Styling approaches (QSS)
- Project structure and organization
- UI code generation workflows
- Figma integration strategies
- Key design patterns
- Best practices

**When to reference**: 
- Creating new UI components
- Styling existing components
- Setting up new editors or dialogs
- Implementing design system changes
- Integrating Figma designs

## Related Documentation

### ../FIGMA_DIAGRAMS.md
Comprehensive collection of 22 architectural diagrams covering:
- Overview & Architecture (6 diagrams)
- Tool-Specific workflows (5 diagrams)
- Core Systems (4 diagrams)
- UI & Editors (3 diagrams)
- Development processes (4 diagrams)

All diagrams are interactive FigJam boards accessible via web links.

**When to reference**:
- Understanding system architecture
- Planning new features
- Onboarding new developers
- Documentation and presentations
- Technical discussions

### ../FIGMA_CODE_CONNECT_EXAMPLES.md
Practical examples of mapping Figma components to code:
- Primary Button Component
- Dialog Editor Tree View
- Color Picker Widget
- Resource List Item
- Property Editor Dialog

Includes:
- Code examples with Figma references
- Mapping workflows
- Component registry
- Best practices
- CI/CD integration ideas

**When to reference**:
- Implementing Figma designs
- Creating new components from designs
- Maintaining design-code consistency
- Setting up Code Connect mappings

## Quick Reference

### Color Tokens
```python
# Dark Theme
BACKGROUND_PRIMARY = "#2D2D30"
TEXT_PRIMARY = "#CCCCCC"
ACCENT_BLUE = "#007ACC"
SUCCESS = "#89D185"
ERROR = "#F48771"
```

### Typography
```python
DEFAULT_FONT = QFont("Segoe UI", 9)
CODE_FONT = QFont("Consolas", 10)
```

### Spacing
```python
SPACING_SM = 4
SPACING_MD = 8
SPACING_LG = 16
```

### Component Pattern
```python
class CustomWidget(QWidget):
    """Brief description.
    
    Figma: ComponentName (Node XXX:YYY)
    """
    valueChanged = Signal(object)
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self._setup_ui()
        self._connect_signals()
```

## Usage with AI Assistants

These rules are designed to be consumed by AI coding assistants (like Cursor, GitHub Copilot, etc.) to maintain consistency when generating or modifying code.

### For AI: Key Guidelines

1. **Always check design_system_rules.md** when creating UI components
2. **Reference FIGMA_DIAGRAMS.md** for architectural context
3. **Follow the component patterns** shown in examples
4. **Use the established color/typography tokens**
5. **Maintain Qt/PyQt6 best practices**
6. **Add Figma references** in docstrings when applicable

### For Developers: Integration

1. Ensure your AI assistant has access to these files
2. Reference specific sections when asking for help
3. Update rules when design system changes
4. Keep Code Connect mappings current

## Contributing

When updating the design system:

1. **Update design_system_rules.md** with new tokens/patterns
2. **Create/update diagrams** in Figma and link in FIGMA_DIAGRAMS.md
3. **Add code examples** to FIGMA_CODE_CONNECT_EXAMPLES.md
4. **Update this README** if new files are added
5. **Communicate changes** to the team

## File Naming Conventions

- `*_rules.md` - Rule sets for specific domains (design, coding, etc.)
- `*_guidelines.md` - Guidelines and best practices
- `*_patterns.md` - Common code patterns and templates

## Maintenance Schedule

- **Review quarterly** - Ensure rules match current codebase
- **Update after major UI changes** - Keep design tokens current
- **Sync with Figma** - Maintain design-code consistency
- **Validate with team** - Ensure rules are practical and followed

---

**Last Updated**: 2026-01-31  
**Maintainer**: PyKotor Team  
**Questions**: See project CONTRIBUTING.md
