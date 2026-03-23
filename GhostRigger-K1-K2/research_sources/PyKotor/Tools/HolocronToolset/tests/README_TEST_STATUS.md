# Holocron Toolset Test Status

## Current Test Execution Status

### Summary
The Holocron Toolset test suite has been examined and configured to properly skip tests that require game installations when those installations are not available.

### Test Requirements

Most editor tests require actual KOTOR I or KOTOR II game installations because:
1. Editors need to load game resources (2DA files, models, textures, etc.)
2. The `HTInstallation` class validates installation paths and requires `chitin.key` files
3. Tests verify editor behavior against real game data formats

### Installation Setup

To run the full test suite, you need to set environment variables pointing to valid game installations:

```powershell
# Windows PowerShell
$Env:K1_PATH = "C:\Path\To\KOTOR"
$Env:K2_PATH = "C:\Path\To\KOTOR2"
```

```bash
# Linux/macOS
export K1_PATH="/path/to/kotor"
export K2_PATH="/path/to/kotor2"
```

The installations must contain:
- `chitin.key` file in the root directory
- Standard game data files (BIFs, ERFs, RIMs)
- `dialog.tlk` talk table

### Running Tests

Run from PyKotor repo root. Use `uv run pytest` (recommended) or `python -m pytest` with an activated venv.

```powershell
# Run all editor tests (will skip if installations not available)
uv run pytest Tools/HolocronToolset/tests/gui/editors/ -v

# Run specific editor test
uv run pytest Tools/HolocronToolset/tests/gui/editors/test_gff_editor.py -v

# See skip reasons
uv run pytest Tools/HolocronToolset/tests/gui/editors/ -v -rs
```

### Test Results Without Installations

When game installations are not available:
- **Skipped**: 3105+ tests (all editor tests requiring installations)
- **Passed**: Tests that don't require installations (e.g., BWM transition integrity tests)
- **Failed**: 0 (tests properly skip instead of failing)

### Modifications Made

1. **conftest.py**: Updated `installation` and `tsl_installation` fixtures to:
   - Check if installation paths exist
   - Check if `chitin.key` file exists
   - Skip tests gracefully if installations are not available
   - Provide clear skip messages

### Next Steps

To get editor tests passing:

1. **Option A - Use Real Installations**:
   - Install KOTOR I and/or KOTOR II
   - Set environment variables to installation paths
   - Run tests

2. **Option B - Create Mock Installation** (Future Work):
   - Create minimal fake installation structure for testing
   - Include minimal required files (empty chitin.key, basic 2DA files, etc.)
   - Place in `tests/test_files/mock_installation/`
   - Update fixtures to use mock installation when real ones unavailable

3. **Option C - Refactor Tests** (Future Work):
   - Separate editor initialization tests from game data tests
   - Create unit tests that don't require installations
   - Use mocking for HTInstallation dependencies

### Test Categories

1. **Installation-Dependent** (Currently Skipping):
   - All GFF editor tests
   - All 2DA editor tests
   - All DLG (dialog) editor tests
   - All ARE (area) editor tests
   - Most other specialized editors

2. **Installation-Independent** (Passing):
   - BWM (walkmesh) transition integrity tests
   - Some model editor initialization tests

### Conclusion

The test suite is now properly configured to skip tests gracefully when installations are not available, preventing false failures. To fully validate the editor functionality, actual KOTOR installations are required.

Date: January 22, 2026
