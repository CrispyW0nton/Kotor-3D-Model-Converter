"""test_live_model_inspect.py — Phase G3 live-data guard-rail
==============================================================

Purpose
-------
Runs the full load pipeline (PyKotor parse → kotor_loader conversion →
world_transform computation → inner-geo classification) against real MDL
files from installed K1 and K2 directories and verifies the resulting
``KotorModel`` passes a set of sanity invariants:

  * Model loads without exception and has a root node.
  * No NaN / ±Inf in any node's ``position``, ``world_position()``, or
    sampled vertex coordinates.
  * Every skin node's ``bone_map`` references nodes that actually exist in
    the model's flat node list.
  * Skin vertices have bone indices in palette range (no out-of-bounds
    entries reaching the GPU).

These checks are intentionally conservative — they don't pin visual
correctness (that needs screenshots), just data-structure sanity.  Their job
is to catch regressions like the "PyKotor wholesale patch breaks K2 skin
nodes" class of bug where the loader silently emits NaN vertices or garbage
bone indices.

Game install paths (Steam defaults):
  K1: ``C:\\Program Files (x86)\\Steam\\steamapps\\common\\swkotor``
  K2: ``C:\\Program Files (x86)\\Steam\\steamapps\\common\\Knights of the
       Old Republic II``

When neither install is present the live tests are ``skipTest()``'d so the
suite stays green on CI / fresh dev boxes.  The template-MDL test still runs
if any ``.mdl`` files are present under ``templates/``.
"""
from __future__ import annotations

import math
import os
import sys
import unittest
from pathlib import Path
from typing import List, Optional, Tuple

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)


# ─────────────────────────────────────────────────────────────────────────────
#  Install discovery
# ─────────────────────────────────────────────────────────────────────────────

K1_PATH = Path(r"C:\Program Files (x86)\Steam\steamapps\common\swkotor")
K2_PATH = Path(
    r"C:\Program Files (x86)\Steam\steamapps\common\Knights of the Old Republic II"
)
TEMPLATE_DIR = Path(_ROOT) / "templates"

# Cap so the test suite stays fast even when Override has thousands of MDLs.
PER_GAME_LIMIT = 5


def _find_mdl_files(base: Path, subfolders: Tuple[str, ...], limit: int) -> List[Path]:
    """Return up to ``limit`` ``.mdl`` files under ``base / subfolder`` (recursive).

    Returns an empty list if ``base`` doesn't exist or no ``.mdl`` files are
    found — the test then skips cleanly.  We intentionally *don't* pull from
    ``chitin.key`` / ``.bif`` archives here: the point of this test is to
    validate the on-disk loader path (Override / extracted models), which is
    what most users will hit first.
    """
    if not base.exists():
        return []
    out: List[Path] = []
    for sub in subfolders:
        d = base / sub
        if not d.exists():
            continue
        for f in d.rglob("*.mdl"):
            out.append(f)
            if len(out) >= limit:
                return out
    return out


def _has_nan_inf(value) -> bool:
    """True if ``value`` is (or contains) NaN or ±Inf.  Scalars and iterables."""
    if value is None:
        return False
    if isinstance(value, (int, float)):
        return not math.isfinite(float(value))
    try:
        return any(not math.isfinite(float(v)) for v in value)
    except (TypeError, ValueError):
        return False


# ─────────────────────────────────────────────────────────────────────────────
#  Test case
# ─────────────────────────────────────────────────────────────────────────────

class TestLiveModelInspect(unittest.TestCase):

    # ---- model-loader lazy import so skip-paths don't pay import cost ----

    def _load(self, mdl_path: Path):
        """Load an MDL and return (model, err_str).

        Imports are done lazily so that a box without moderngl or PyKotor
        dependencies can still run the earlier unit tests (skinning identity,
        etc.) without pulling in the full loader stack at module import time.
        """
        from src.core.kotor_loader import load_model_from_file
        try:
            model = load_model_from_file(str(mdl_path))
            return model, None
        except Exception as exc:  # pragma: no cover — exercised only on real bugs
            return None, f"{type(exc).__name__}: {exc}"

    # ---- shared validation ------------------------------------------------

    def _validate_model(self, model, label: str) -> None:
        """Run the full set of data-sanity invariants on a loaded model."""
        self.assertIsNotNone(model, f"{label}: loader returned None")
        self.assertIsNotNone(model.root_node, f"{label}: no root node")

        nodes = list(model.all_nodes())
        self.assertGreater(len(nodes), 0, f"{label}: model has zero nodes")

        all_names_lower = {n.name.lower() for n in nodes if n.name}

        for node in nodes:
            tag = f"{label} node='{node.name}'"

            # ── transforms are finite ──────────────────────────────────────
            self.assertFalse(
                _has_nan_inf(node.position),
                f"{tag}: non-finite position {node.position!r}",
            )
            wp = node.world_position()
            self.assertFalse(
                _has_nan_inf(wp),
                f"{tag}: non-finite world_position {wp!r}",
            )

            # ── vertex spot-check (first 10 verts) ────────────────────────
            for vi, v in enumerate(node.vertices[:10]):
                self.assertFalse(
                    _has_nan_inf(v),
                    f"{tag}: non-finite vertex[{vi}] {v!r}",
                )

            # ── skin-specific checks ──────────────────────────────────────
            if node.is_skin and node.bone_map:
                n_slots = len(node.bone_map)

                for slot, bname in enumerate(node.bone_map):
                    if not bname:
                        continue
                    self.assertIn(
                        bname.lower(), all_names_lower,
                        f"{tag}: bone_map[{slot}]='{bname}' not in model",
                    )

                for vi, vsd in enumerate(node.skin_data[:20]):
                    for inf in vsd.influences:
                        self.assertGreaterEqual(
                            inf.bone_index, 0,
                            f"{tag} v{vi}: negative bone_index "
                            f"{inf.bone_index}",
                        )
                        self.assertLess(
                            inf.bone_index, n_slots,
                            f"{tag} v{vi}: bone_index {inf.bone_index} "
                            f">= palette {n_slots}",
                        )
                        self.assertFalse(
                            _has_nan_inf(inf.weight),
                            f"{tag} v{vi}: non-finite weight {inf.weight}",
                        )

    # ---- suites -----------------------------------------------------------

    def test_templates(self) -> None:
        """Validate any ``.mdl`` files in ``templates/`` (always-on)."""
        if not TEMPLATE_DIR.exists():
            self.skipTest("no templates/ directory")
        mdls = list(TEMPLATE_DIR.glob("*.mdl"))
        if not mdls:
            self.skipTest("no *.mdl files under templates/")
        for mdl in mdls:
            with self.subTest(mdl=mdl.name):
                model, err = self._load(mdl)
                self.assertIsNone(err,
                                  f"load error for {mdl.name}: {err}")
                self._validate_model(model, mdl.name)

    def test_k1_override_models(self) -> None:
        """Spot-check up to 5 ``.mdl`` files under the K1 Override folder."""
        if not K1_PATH.exists():
            self.skipTest(f"K1 install not found at {K1_PATH}")
        mdls = _find_mdl_files(K1_PATH, ("Override",), PER_GAME_LIMIT)
        if not mdls:
            self.skipTest("no .mdl files under K1 Override")
        for mdl in mdls:
            with self.subTest(mdl=mdl.name):
                model, err = self._load(mdl)
                self.assertIsNone(err,
                                  f"load error for {mdl.name}: {err}")
                self._validate_model(model, f"K1:{mdl.name}")

    def test_k2_override_models(self) -> None:
        """Spot-check up to 5 ``.mdl`` files under the K2 Override folder."""
        if not K2_PATH.exists():
            self.skipTest(f"K2 install not found at {K2_PATH}")
        mdls = _find_mdl_files(K2_PATH, ("Override",), PER_GAME_LIMIT)
        if not mdls:
            self.skipTest("no .mdl files under K2 Override")
        for mdl in mdls:
            with self.subTest(mdl=mdl.name):
                model, err = self._load(mdl)
                self.assertIsNone(err,
                                  f"load error for {mdl.name}: {err}")
                self._validate_model(model, f"K2:{mdl.name}")


if __name__ == "__main__":
    unittest.main()
