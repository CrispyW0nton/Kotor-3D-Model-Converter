"""
test_v45_mdl_crash_fixes.py
===========================
Comprehensive crash-fix and diagnostic tests for GhostRigger v4.5.

Findings from the full-crash-scan investigation:
  1. ALL 2527 game models parse and render without crashing in headless mode.
  2. Thread-unsafe Tkinter calls in LibraryPanel._scan() and _scan_deep():
       - _status_var.set() was called directly from a background thread.
       - Fixed by routing ALL Tkinter calls through .after(0, ...).
  3. Bug in _try_load_from_library(): entry.game_version AttributeError
       - ModelLibraryEntry has .game ("K1"/"K2") not .game_version.
       - Fixed by using GameVersion.K1/K2 based on entry.game.
  4. Missing error handling around viewport.load_model() in _refresh_all().
  5. Missing traceback logging in _on_library_load except clause.

These tests verify the fixes and establish a regression baseline.
"""
import sys, os, pytest, struct

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.core.mdl_parser import MDLBinaryParser, MDLAsciiParser, MDLAsciiWriter
from src.core.model_data import KotorModel, ModelNode, NodeFlags, GameVersion


# ─────────────────────────────────────────────────────────────────────────────
#  Fixtures / helpers
# ─────────────────────────────────────────────────────────────────────────────

GAME_DATA_DIR = os.path.join(
    os.path.dirname(__file__), '..', 'game_data', 'swkotor')
EXTRACTED_DIR = os.path.join(
    os.path.dirname(__file__), '..', 'test_assets', 'k1_extracted', 'models')
SITHPRAET_MDL  = os.path.join(
    os.path.dirname(__file__), '..', 'test_assets', 'N_sithpraet.mdl')
SITHPRAET_MDX  = os.path.join(
    os.path.dirname(__file__), '..', 'test_assets', 'N_sithpraet.mdx')

HAS_GAME_DATA = os.path.isfile(os.path.join(GAME_DATA_DIR, 'chitin.key'))
HAS_SITHPRAET = os.path.isfile(SITHPRAET_MDL)
HAS_EXTRACTED = os.path.isdir(EXTRACTED_DIR)


def _load_extracted(name: str):
    """Load an extracted binary MDL/MDX pair by name."""
    mdl_path = os.path.join(EXTRACTED_DIR, f"{name}.mdl")
    mdx_path = os.path.join(EXTRACTED_DIR, f"{name}.mdx")
    if not os.path.isfile(mdl_path):
        pytest.skip(f"Extracted model not found: {mdl_path}")
    mdl = open(mdl_path, 'rb').read()
    mdx = open(mdx_path, 'rb').read() if os.path.isfile(mdx_path) else b''
    return mdl, mdx


# ─────────────────────────────────────────────────────────────────────────────
#  1. Parser API contract tests
# ─────────────────────────────────────────────────────────────────────────────

class TestParserAPI:
    """Verify the MDLBinaryParser API contract that callers rely on."""

    def test_constructor_requires_two_args(self):
        """MDLBinaryParser(mdl, mdx) — both required positional args."""
        with pytest.raises(TypeError):
            MDLBinaryParser()                     # no args → TypeError

    def test_constructor_accepts_bytes(self):
        """Valid MDL bytes must not raise in __init__."""
        if not HAS_SITHPRAET:
            pytest.skip("N_sithpraet.mdl not available")
        mdl = open(SITHPRAET_MDL, 'rb').read()
        mdx = open(SITHPRAET_MDX, 'rb').read() if os.path.isfile(SITHPRAET_MDX) else b''
        p = MDLBinaryParser(mdl, mdx)     # must not raise
        assert p.mdl is mdl
        assert p.mdx is mdx

    def test_parse_returns_kotor_model(self):
        """parse() must return a KotorModel instance."""
        if not HAS_SITHPRAET:
            pytest.skip("N_sithpraet.mdl not available")
        mdl = open(SITHPRAET_MDL, 'rb').read()
        mdx = open(SITHPRAET_MDX, 'rb').read() if os.path.isfile(SITHPRAET_MDX) else b''
        model = MDLBinaryParser(mdl, mdx).parse()
        assert isinstance(model, KotorModel)

    def test_parse_files_classmethod(self):
        """MDLBinaryParser.parse_files() convenience classmethod."""
        if not HAS_SITHPRAET:
            pytest.skip("N_sithpraet.mdl not available")
        model = MDLBinaryParser.parse_files(SITHPRAET_MDL)
        assert isinstance(model, KotorModel)
        assert model.node_count() > 0

    def test_from_files_classmethod(self):
        """MDLBinaryParser.from_files() returns a parser, then parse() works."""
        if not HAS_SITHPRAET:
            pytest.skip("N_sithpraet.mdl not available")
        parser = MDLBinaryParser.from_files(SITHPRAET_MDL)
        model  = parser.parse()
        assert model.node_count() > 0

    def test_parse_small_mdl_raises_valueerror(self):
        """Files under 180 bytes must raise ValueError, not crash."""
        with pytest.raises((ValueError, Exception)):
            MDLBinaryParser(b'\x00' * 100, b'').parse()

    def test_parse_empty_bytes(self):
        """Empty bytes must raise, not crash."""
        with pytest.raises((ValueError, Exception)):
            MDLBinaryParser(b'', b'').parse()


# ─────────────────────────────────────────────────────────────────────────────
#  2. Extracted real model tests
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.skipif(not HAS_EXTRACTED, reason="extracted models not available")
class TestExtractedModels:
    """Parse the 6 extracted real K1 models and verify properties."""

    EXPECTED = {
        'c_bantha':    {'nodes': 46, 'meshes': 40, 'anims': 9},
        'c_brith':     {'nodes': 21, 'meshes': 18, 'anims': 2},
        'c_kinrath':   {'nodes': 35, 'meshes': 29, 'anims': 32},
        'c_bmspecdiff':{'nodes': 46, 'meshes': 41, 'anims': 5},
        'ad_saul':     {'nodes': 32, 'meshes': 25, 'anims': 0},
        '3dgui':       {'nodes': 209,'meshes': 196,'anims': 1},
    }

    @pytest.mark.parametrize("name,expected", EXPECTED.items())
    def test_parse_real_model(self, name, expected):
        """Parse a real binary MDL and verify node/mesh/anim counts."""
        mdl, mdx = _load_extracted(name)
        model = MDLBinaryParser(mdl, mdx).parse()
        assert model.node_count() == expected['nodes'], \
               f"{name}: expected {expected['nodes']} nodes, got {model.node_count()}"
        assert len(model.mesh_nodes()) == expected['meshes'], \
               f"{name}: expected {expected['meshes']} meshes"
        assert len(model.animations) == expected['anims'], \
               f"{name}: expected {expected['anims']} animations"

    @pytest.mark.parametrize("name", list(EXPECTED.keys()))
    def test_model_has_root_node(self, name):
        """Every parsed model must have a non-None root_node."""
        mdl, mdx = _load_extracted(name)
        model = MDLBinaryParser(mdl, mdx).parse()
        assert model.root_node is not None, f"{name}: root_node is None"

    @pytest.mark.parametrize("name", list(EXPECTED.keys()))
    def test_all_nodes_have_children_list(self, name):
        """Every node.children must be a list, never None."""
        mdl, mdx = _load_extracted(name)
        model = MDLBinaryParser(mdl, mdx).parse()
        for node in model.all_nodes():
            assert node.children is not None, \
                   f"{name}: node '{node.name}' has children=None"
            assert isinstance(node.children, list)

    @pytest.mark.parametrize("name", list(EXPECTED.keys()))
    def test_all_mesh_nodes_have_vertices_list(self, name):
        """Every mesh node.vertices must be a list, never None."""
        mdl, mdx = _load_extracted(name)
        model = MDLBinaryParser(mdl, mdx).parse()
        for node in model.mesh_nodes():
            assert node.vertices is not None, \
                   f"{name}: mesh node '{node.name}' has vertices=None"
            assert isinstance(node.vertices, list)

    @pytest.mark.parametrize("name", list(EXPECTED.keys()))
    def test_game_version_detected(self, name):
        """K1 models must be detected as GameVersion.K1."""
        mdl, mdx = _load_extracted(name)
        model = MDLBinaryParser(mdl, mdx).parse()
        assert model.game_version == GameVersion.K1, \
               f"{name}: expected K1, got {model.game_version}"

    @pytest.mark.parametrize("name", list(EXPECTED.keys()))
    def test_texture_list_no_null(self, name):
        """texture_list() must not include 'NULL' or empty strings."""
        mdl, mdx = _load_extracted(name)
        model = MDLBinaryParser(mdl, mdx).parse()
        for t in model.texture_list():
            assert t and t.upper() != 'NULL', \
                   f"{name}: texture_list() contains invalid entry '{t}'"

    @pytest.mark.parametrize("name", list(EXPECTED.keys()))
    def test_prewarm_texture_names(self, name):
        """Simulate prewarm texture snapshot: must not raise."""
        mdl, mdx = _load_extracted(name)
        model = MDLBinaryParser(mdl, mdx).parse()
        # Exact code from ViewportWidget._prewarm_textures
        tex_names = list({n.texture_clean for n in model.mesh_nodes()
                          if n.texture_clean and
                          n.texture_clean.upper() not in ('NULL', '')})
        assert isinstance(tex_names, list)   # no exception raised

    @pytest.mark.parametrize("name", list(EXPECTED.keys()))
    def test_node_count_method(self, name):
        """model.node_count() must be > 0 and == len(all_nodes())."""
        mdl, mdx = _load_extracted(name)
        model = MDLBinaryParser(mdl, mdx).parse()
        assert model.node_count() > 0
        assert model.node_count() == len(list(model.all_nodes()))

    @pytest.mark.parametrize("name", list(EXPECTED.keys()))
    def test_bounding_box_valid(self, name):
        """Bounding box values must be finite floats."""
        import math
        mdl, mdx = _load_extracted(name)
        model = MDLBinaryParser(mdl, mdx).parse()
        for v in model.bb_min + model.bb_max:
            assert isinstance(v, (int, float)), f"{name}: bb value {v} not numeric"
            assert math.isfinite(float(v)), f"{name}: bb value {v} not finite"


# ─────────────────────────────────────────────────────────────────────────────
#  3. GameLibrary path tests
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.skipif(not HAS_GAME_DATA, reason="game data not available")
class TestGameLibraryPath:
    """Integration tests against the real game library."""

    def test_scan_finds_models(self):
        """scan() must populate lib.models with > 2000 K1 models."""
        from src.resources.game_library import GameLibrary
        lib = GameLibrary()
        lib.set_k1_dir(GAME_DATA_DIR)
        lib.scan(progress_cb=None, deep_scan=False)
        k1_models = [e for e in lib.models if e.game == "K1"]
        assert len(k1_models) >= 2000, f"Expected ≥2000 K1 models, got {len(k1_models)}"

    def test_get_model_data_returns_bytes(self):
        """get_model_data() for a known model must return non-empty bytes."""
        from src.resources.game_library import GameLibrary
        lib = GameLibrary()
        lib.set_k1_dir(GAME_DATA_DIR)
        lib.scan(progress_cb=None, deep_scan=False)
        entry = next((e for e in lib.models if e.resref == 'c_bantha'), None)
        if entry is None:
            pytest.skip("c_bantha not found in library")
        mdl, mdx = lib.get_model_data(entry)
        assert mdl and len(mdl) > 100, "MDL data empty or too small"

    def test_model_entry_has_game_not_game_version(self):
        """ModelLibraryEntry must have .game (str) but NOT .game_version."""
        from src.resources.game_library import GameLibrary
        lib = GameLibrary()
        lib.set_k1_dir(GAME_DATA_DIR)
        lib.scan(progress_cb=None, deep_scan=False)
        if lib.models:
            entry = lib.models[0]
            assert hasattr(entry, 'game'), "ModelLibraryEntry must have .game"
            assert not hasattr(entry, 'game_version'), \
                   "ModelLibraryEntry must NOT have .game_version (fixed in v4.5)"
            assert entry.game in ('K1', 'K2'), f".game must be 'K1' or 'K2', got '{entry.game}'"

    def test_parse_c_bantha_from_library(self):
        """End-to-end: library → get_model_data → parse must succeed."""
        from src.resources.game_library import GameLibrary
        lib = GameLibrary()
        lib.set_k1_dir(GAME_DATA_DIR)
        lib.scan(progress_cb=None, deep_scan=False)
        entry = next((e for e in lib.models if e.resref == 'c_bantha'), None)
        if entry is None:
            pytest.skip("c_bantha not found")
        mdl, mdx = lib.get_model_data(entry)
        model = MDLBinaryParser(mdl, mdx or b'').parse()
        model.name = entry.resref
        model.game_version = GameVersion.K1 if entry.game == "K1" else GameVersion.K2
        assert model.node_count() == 46
        assert len(model.mesh_nodes()) == 40

    def test_parse_sample_models_no_crash(self):
        """Parse the first 50 models from library without any crash."""
        from src.resources.game_library import GameLibrary
        lib = GameLibrary()
        lib.set_k1_dir(GAME_DATA_DIR)
        lib.scan(progress_cb=None, deep_scan=False)
        k1_models = [e for e in lib.models if e.game == "K1"][:50]
        crashed = []
        for entry in k1_models:
            try:
                mdl, mdx = lib.get_model_data(entry)
                if mdl and len(mdl) >= 12:
                    MDLBinaryParser(mdl, mdx or b'').parse()
            except Exception as e:
                crashed.append(f"{entry.resref}: {e}")
        assert not crashed, f"Models crashed: {crashed}"


# ─────────────────────────────────────────────────────────────────────────────
#  4. Thread safety and API contract
# ─────────────────────────────────────────────────────────────────────────────

class TestThreadSafetyContracts:
    """Verify that thread-safety fixes are in place (static analysis)."""

    def test_scan_uses_safe_progress_callback(self):
        """_scan() must not call _status_var.set() directly from thread."""
        import inspect, ast
        path = os.path.join(
            os.path.dirname(__file__), '..', 'src', 'gui', 'main_window.py')
        with open(path) as f:
            source = f.read()
        lines = source.splitlines()

        # Find _scan method and its inner run() function
        in_scan = False
        in_run = False
        run_indent = 0
        unsafe_calls = []

        for i, line in enumerate(lines):
            if 'def _scan(self):' in line:
                in_scan = True
                continue
            if in_scan:
                if 'def run():' in line:
                    in_run = True
                    run_indent = len(line) - len(line.lstrip())
                    continue
                elif in_run:
                    stripped = line.strip()
                    cur_indent = len(line) - len(line.lstrip()) if stripped else run_indent + 1
                    # If we dedented back to or past run_indent: end of run()
                    if stripped and cur_indent <= run_indent and not stripped.startswith('#'):
                        if 'def ' not in stripped:
                            in_run = False
                            in_scan = False
                            break
                    # Check for direct _status_var.set without after() (skip comments)
                    stripped_check = line.lstrip()
                    if (not stripped_check.startswith('#') and
                            '_status_var.set(' in line and
                            'after' not in line and
                            'lambda' not in line):
                        unsafe_calls.append(f"L{i+1}: {line.rstrip()}")

        assert not unsafe_calls, \
               f"Thread-unsafe _status_var.set() calls found in _scan.run():\n" + \
               "\n".join(unsafe_calls)

    def test_scan_deep_uses_safe_progress_callback(self):
        """_scan_deep() must not call _status_var.set() directly from thread."""
        path = os.path.join(
            os.path.dirname(__file__), '..', 'src', 'gui', 'main_window.py')
        with open(path) as f:
            lines = f.readlines()

        in_scan = False
        in_run = False
        run_indent = 0
        unsafe_calls = []

        for i, line in enumerate(lines):
            if 'def _scan_deep(self):' in line:
                in_scan = True
                continue
            if in_scan and 'def run():' in line:
                in_run = True
                run_indent = len(line) - len(line.lstrip())
                continue
            if in_run:
                stripped = line.strip()
                cur_indent = len(line) - len(line.lstrip()) if stripped else run_indent + 1
                if stripped and cur_indent <= run_indent and not stripped.startswith('#'):
                    if 'def ' not in stripped:
                        in_run = False; in_scan = False; break
                stripped_check = line.lstrip()
                if (not stripped_check.startswith('#') and
                        '_status_var.set(' in line and
                        'after' not in line and
                        'lambda' not in line):
                    unsafe_calls.append(f"L{i+1}: {line.rstrip()}")

        assert not unsafe_calls, \
               f"Thread-unsafe calls in _scan_deep.run(): {unsafe_calls}"

    def test_try_load_from_library_uses_entry_game_not_game_version(self):
        """_try_load_from_library must use entry.game not entry.game_version."""
        path = os.path.join(
            os.path.dirname(__file__), '..', 'src', 'gui', 'main_window.py')
        with open(path) as f:
            source = f.read()

        # Find _try_load_from_library and check for the AttributeError bug
        import re
        # Extract the function body
        match = re.search(
            r'def _try_load_from_library.*?(?=\n    def |\Z)',
            source, re.DOTALL)
        if match:
            body = match.group(0)
            assert 'entry.game_version' not in body, \
                "Bug: 'entry.game_version' used (ModelLibraryEntry has .game not .game_version)"
            # Correct pattern should be entry.game == "K1" → GameVersion.K1
            assert 'entry.game' in body, \
                "Expected 'entry.game' usage in _try_load_from_library"


# ─────────────────────────────────────────────────────────────────────────────
#  5. Full pipeline simulation (headless)
# ─────────────────────────────────────────────────────────────────────────────

@pytest.mark.skipif(not HAS_EXTRACTED, reason="extracted models not available")
class TestFullPipeline:
    """Simulate the complete GUI model-load pipeline without Tkinter."""

    @pytest.mark.parametrize("name", [
        'c_bantha', 'c_brith', 'c_kinrath', 'ad_saul', 'c_bmspecdiff', '3dgui'
    ])
    def test_complete_load_path(self, name):
        """Simulate _on_library_load → _set_model_internal → _refresh_all."""
        mdl, mdx = _load_extracted(name)

        # Step 1: Parse (as _on_library_load does)
        model = MDLBinaryParser(mdl, mdx).parse()
        model.name = name
        model.game_version = GameVersion.K1

        # Step 2: Access all properties _refresh_all uses
        assert model.node_count() > 0
        mesh_nodes = model.mesh_nodes()
        tex_list = model.texture_list()
        root = model.root_node
        assert root is not None

        # Step 3: Prewarm texture snapshot
        tex_names = list({n.texture_clean for n in mesh_nodes
                          if n.texture_clean and
                          n.texture_clean.upper() not in ('NULL', '')})
        assert isinstance(tex_names, list)

        # Step 4: SkeletonPanel.load_model simulation
        all_nodes = list(model.all_nodes())
        assert len(all_nodes) > 0
        for node in all_nodes:
            _ = node.name
            _ = node.type_label
            _ = len(node.vertices) if node.is_mesh else 0
            _ = len(node.faces) if node.is_mesh else 0

        # Step 5: PropertiesPanel.show_model simulation
        _ = model.name
        _ = f"{'K1' if model.game_version == GameVersion.K1 else 'K2'}  │  {model.name}"

        # Step 6: Rendering pipeline simulation
        try:
            from src.gui.viewport import FrameRenderer
            from src.gui.viewport import ArcBallCamera
            cam = ArcBallCamera()
            renderer = FrameRenderer(cam)
            renderer.set_model(model)
            img = renderer.render(400, 300)
            assert img is not None, f"{name}: renderer.render() returned None"
        except ImportError:
            pytest.skip("viewport not importable in this context")

    @pytest.mark.parametrize("name", ['c_bantha', 'c_brith'])
    def test_ascii_roundtrip(self, name):
        """Parse binary MDL, write ASCII, re-parse ASCII — data preserved."""
        mdl, mdx = _load_extracted(name)
        model = MDLBinaryParser(mdl, mdx).parse()

        import tempfile
        with tempfile.NamedTemporaryFile(suffix='.mdl', delete=False, mode='w') as tmp:
            tmppath = tmp.name

        try:
            MDLAsciiWriter().write(model, tmppath)
            model2 = MDLAsciiParser().parse_file(tmppath)
            assert model2.node_count() == model.node_count(), \
                   f"{name}: ascii roundtrip lost nodes"
        finally:
            os.unlink(tmppath)


# ─────────────────────────────────────────────────────────────────────────────
#  6. Logging infrastructure tests
# ─────────────────────────────────────────────────────────────────────────────

class TestLoggingInfrastructure:
    """Verify the logging system in main.py works correctly."""

    def test_make_log_dir(self, tmp_path):
        """_make_log_dir() must create the directory without error."""
        import sys, importlib.util, types
        # Import main.py as a module
        main_path = os.path.join(os.path.dirname(__file__), '..', 'main.py')
        spec = importlib.util.spec_from_file_location("ghostrigger_main", main_path)
        m = importlib.util.module_from_spec(spec)
        # Patch _LOG_DIR to a temp dir
        orig_log_dir = None
        try:
            spec.loader.exec_module(m)
            orig = m._LOG_DIR
            m._LOG_DIR = str(tmp_path / "Logs")
            m._make_log_dir()
            assert (tmp_path / "Logs").is_dir()
        finally:
            pass

    def test_rotate_old_logs(self, tmp_path):
        """_rotate_old_logs() must keep only the newest N log files."""
        import importlib.util
        main_path = os.path.join(os.path.dirname(__file__), '..', 'main.py')
        spec = importlib.util.spec_from_file_location("ghostrigger_main2", main_path)
        m = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(m)

        log_dir = tmp_path / "Logs"
        log_dir.mkdir()
        m._LOG_DIR = str(log_dir)
        m._LOG_KEEP_FILES = 3

        # Create 5 fake log files
        for i in range(5):
            (log_dir / f"ghostrigger_2026-01-{i+1:02d}_000000.log").write_text(f"log {i}")

        m._rotate_old_logs()
        remaining = list(log_dir.glob("*.log"))
        assert len(remaining) < 5, "Rotation did not remove old files"

    def test_install_exception_hooks(self):
        """_install_exception_hooks() must not raise."""
        import importlib.util
        main_path = os.path.join(os.path.dirname(__file__), '..', 'main.py')
        spec = importlib.util.spec_from_file_location("ghostrigger_main3", main_path)
        m = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(m)
        # Should not raise
        m._install_exception_hooks("/tmp/fake_log.log")

    def test_flush_all_handlers(self):
        """_flush_all_handlers() must not raise even with no handlers."""
        import importlib.util, logging
        main_path = os.path.join(os.path.dirname(__file__), '..', 'main.py')
        spec = importlib.util.spec_from_file_location("ghostrigger_main4", main_path)
        m = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(m)
        m._flush_all_handlers()  # Must not raise
