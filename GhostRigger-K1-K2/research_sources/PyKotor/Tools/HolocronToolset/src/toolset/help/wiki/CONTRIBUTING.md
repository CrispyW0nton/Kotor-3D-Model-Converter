# Contributing to PyKotor

Thank you for your interest in contributing to PyKotor! This guide covers development setup, coding standards, and the contribution workflow.

## Table of Contents

- [Prerequisites](#prerequisites)
- [Development Setup](#development-setup)
- [Development Workflow](#development-workflow)
- [Code Standards](#code-standards)
- [Testing](#testing)
- [Submitting Changes](#submitting-changes)
- [Resources](#resources)

## Prerequisites

- **Python 3.8+** (3.9+ recommended for development)
- **Git** for version control
- A code editor with Python support (VS Code, PyCharm, etc.)

## Development Setup

### 1. Fork and Clone

```bash
git clone https://github.com/YOUR_USERNAME/PyKotor.git
cd PyKotor
```

**Faster clone (if full clone is slow or stalls):** The repository is large (~380 MB). If the clone hangs around 8–15%, use a shallow clone:

```bash
# Shallow clone: only latest commit (fast, ~50–100 MB)
git clone --depth 1 https://github.com/YOUR_USERNAME/PyKotor.git
cd PyKotor
```

To later fetch full history if needed (e.g. for bisect): `git fetch --unshallow`.

Optional: clone without blob content first, then fetch as needed:

```bash
git clone --filter=blob:none --sparse https://github.com/YOUR_USERNAME/PyKotor.git
cd PyKotor
```

### 2. Choose Your Setup Method

**Option A: Using uv (Recommended - Fastest)**

Install uv from [astral-sh/uv installation](https://docs.astral.sh/uv/getting-started/installation/).

Run tools with `--with-editable` to use your local source:

```bash
# PyKotor CLI
uvx --with-editable Libraries/PyKotor pykotor --help

# Tools (add --with-editable for each package you're developing)
uvx --with-editable Libraries/PyKotor --with-editable Tools/HolocronToolset holocrontoolset
uvx --with-editable Libraries/PyKotor --with-editable Tools/HoloPatcher holopatcher
uvx --with-editable Libraries/PyKotor --with-editable Tools/KotorDiff kotordiff
```

Or run directly from source:

```bash
uv run --directory Libraries/PyKotor/src --module pykotor --help
uv run --directory Tools/HolocronToolset/src --module toolset
uv run --directory Tools/HoloPatcher/src --module holopatcher
```

To install packages in editable mode with uv:

```bash
uv pip install -e "Libraries/PyKotor[all,dev]"
uv pip install -e "Tools/HolocronToolset"
uv pip install -e "Tools/HoloPatcher"
uv pip install -e "Tools/KotorDiff"
```

**Option B: Using pip with venv**

```bash
# Windows
python -m venv .venv
.venv\Scripts\Activate.ps1
python -m ensurepip
python -m pip install --upgrade pip
python -m pip install -r Tools/HolocronToolset/requirements.txt
python Tools/HolocronToolset/src/toolset/__main__.py
# Repeat for HoloPatcher, KotorDiff, etc. as needed

# macOS/Linux
python3 -m venv .venv
source .venv/bin/activate
python3 -m ensurepip
python3 -m pip install --upgrade pip
python3 -m pip install -r Tools/HolocronToolset/requirements.txt
python3 Tools/HolocronToolset/src/toolset/__main__.py
```

Or install in editable mode:

```bash
# Windows
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e "Libraries/PyKotor[all,dev]"
python -m pip install -e Tools/HolocronToolset -e Tools/HoloPatcher
# holocrontoolset, holopatcher should now be on PATH

# macOS/Linux
python3 -m venv .venv
source .venv/bin/activate
python3 -m pip install -e "Libraries/PyKotor[all,dev]"
python3 -m pip install -e Tools/HolocronToolset -e Tools/HoloPatcher
# holocrontoolset, holopatcher should now be on PATH
```

**Option C: Using Poetry**

```bash
poetry install --with dev
poetry shell
```

### 3. Verify Installation

```bash
# Check library import
python -c "import pykotor; print('PyKotor installed successfully')"

# Check tools (if installed via pip/pipx)
holocrontoolset --version
holopatcher --version
kotordiff --version  # or kotordiff --version

# PyKotor CLI (included with pykotor package)
pykotor --help
pykotorcli --help
```

## Development Workflow

### 1. Create a Feature Branch

```bash
git checkout -b feature/your-feature-name
```

Use meaningful branch names:
- `feature/` for new features
- `fix/` for bug fixes
- `docs/` for documentation
- `refactor/` for code refactoring

### 2. Make Your Changes

- Write clean, readable code following project conventions
- Add tests for new functionality
- Update documentation as needed
- Keep commits focused and atomic

### 3. Test Your Changes

Run the full test suite before committing:

```bash
# Run tests
pytest

# Run with coverage
pytest --cov=pykotor --cov-report=html
```

### 4. Check Code Quality

```bash
# Lint code
ruff check .

# Auto-fix linting issues
ruff check --fix .

# Format code
ruff format .

# Type check
mypy Libraries/PyKotor/src/pykotor
```

### 5. Commit Your Changes

Follow [Conventional Commits](https://www.conventionalcommits.org/):

```bash
git add .
git commit -m "feat: add new feature"
```

Commit types:
- `feat:` - New feature
- `fix:` - Bug fix
- `docs:` - Documentation changes
- `style:` - Code style changes (formatting, missing semi colons, etc)
- `refactor:` - Code refactoring
- `test:` - Adding or updating tests
- `chore:` - Maintenance tasks

### 6. Push and Create Pull Request

```bash
git push origin feature/your-feature-name
```

Then create a pull request on GitHub with:
- Clear description of changes
- Reference to related issues
- Screenshots for UI changes

## Code Standards

### Python Style

- **Python Version**: Support Python 3.8+ (avoid 3.8+ only features)
- **Code Style**: Follow [PEP 8](https://pep8.org/)
- **Docstrings**: Use [Google style](https://google.github.io/styleguide/pyguide.html#38-comments-and-docstrings)
- **Type Hints**: Add type hints where appropriate (see [PEP 484](https://www.python.org/dev/peps/pep-0484/))
- **Line Length**: 120 characters maximum

### Example Code

```python
from typing import Optional


def process_resource(resource_name: str, game_path: Optional[str] = None) -> bool:
    """Process a game resource file.
    
    Args:
        resource_name: Name of the resource to process.
        game_path: Optional path to game installation.
        
    Returns:
        True if processing succeeded, False otherwise.
        
    Raises:
        ValueError: If resource_name is empty.
    """
    if not resource_name:
        raise ValueError("resource_name cannot be empty")
    
    # Implementation here
    return True
```

### Code Quality Tools

We use the following tools:

- **ruff**: Fast Python linter and formatter
- **mypy**: Static type checker
- **pytest**: Testing framework

Run all checks:

```bash
# Lint
ruff check .

# Format
ruff format .

# Type check
mypy Libraries/PyKotor/src/pykotor

# Test
pytest
```

## Testing

### Running Tests

**Basic test run:**
```bash
pytest
```

**With verbose output:**
```bash
pytest -v
```

**With coverage report:**
```bash
pytest --cov=pykotor --cov-report=html
```

**Run specific tests:**
```bash
# Specific file
pytest tests/test_specific.py

# Specific test
pytest tests/test_specific.py::test_function_name

# Pattern matching
pytest -k "test_pattern"
```

### Writing Tests

Place tests in the `tests/` directory following these conventions:

**File naming:**
- `test_*.py` for test files
- Match the module being tested: `pykotor/module.py` → `tests/test_module.py`

**Test naming:**
- Use descriptive names: `test_function_name_with_valid_input()`
- Use `test_` prefix for all test functions

**Example test:**

```python
import pytest
from pykotor.resource.type import ResourceType


def test_resource_type_from_extension():
    """Test ResourceType creation from file extension."""
    assert ResourceType.from_extension("utc") == ResourceType.UTC
    assert ResourceType.from_extension(".utc") == ResourceType.UTC


def test_resource_type_invalid_extension():
    """Test ResourceType with invalid extension raises error."""
    with pytest.raises(ValueError):
        ResourceType.from_extension("invalid")
```

## Submitting Changes

### Before Submitting

Ensure your changes:
- [ ] Pass all tests (`pytest`)
- [ ] Pass linting (`ruff check .`)
- [ ] Are formatted correctly (`ruff format .`)
- [ ] Include type hints where appropriate
- [ ] Have docstrings for public APIs
- [ ] Include tests for new functionality
- [ ] Update relevant documentation

### Pull Request Guidelines

**Title:**
- Use conventional commit format: `feat: add new feature`
- Be descriptive but concise

**Description:**
- Explain what changes were made and why
- Reference related issues: `Fixes #123` or `Relates to #456`
- Include screenshots for UI changes
- List any breaking changes

**Review Process:**
1. Automated checks must pass (linting, tests, type checking)
2. At least one maintainer review required
3. Address review feedback promptly
4. Keep the PR focused on a single concern

### After Approval

- Maintainers will merge your PR
- Your changes will be included in the next release
- You'll be credited in the release notes

## Resources

- **[Python Style Guide (PEP 8)](https://pep8.org/)** - Python coding conventions
- **[Google Python Style Guide](https://google.github.io/styleguide/pyguide.html)** - Docstring conventions
- **[Conventional Commits](https://www.conventionalcommits.org/)** - Commit message format
- **[Project Wiki](https://github.com/OldRepublicDevs/PyKotor/wiki)** - Additional documentation
- **[Issue Tracker](https://github.com/OldRepublicDevs/PyKotor/issues)** - Report bugs or request features

### Getting Help

If you need help:
- Check existing [documentation](https://github.com/OldRepublicDevs/PyKotor/tree/master/Libraries/PyKotor/docs)
- Search [closed issues](https://github.com/OldRepublicDevs/PyKotor/issues?q=is%3Aissue+is%3Aclosed)
- Open a [new issue](https://github.com/OldRepublicDevs/PyKotor/issues/new) with the question label
- Review similar code in the codebase

Thank you for contributing to PyKotor!

