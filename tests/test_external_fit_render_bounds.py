from __future__ import annotations

import pathlib
import sys
from types import SimpleNamespace


_REPO_ROOT = pathlib.Path(__file__).resolve().parents[1]
for _project in ("GhostRigger.Core.Math", "GhostRigger.Core.Workflow"):
    _payload = _REPO_ROOT / "native" / _project / "Python"
    if str(_payload) not in sys.path:
        sys.path.insert(0, str(_payload))

from src.core.characters import headless_body_workflow as wf  # noqa: E402


class _Model:
    def __init__(self, node: SimpleNamespace) -> None:
        self.node = node
        self.bb_min = (-99.0, -99.0, -99.0)
        self.bb_max = (99.0, 99.0, 99.0)
        self._gr_render_bounds = (self.bb_min, self.bb_max)
        self._gr_bounds_prepared = True

    def all_nodes(self):
        return [self.node]


def test_external_fit_transform_refreshes_prepared_render_bounds() -> None:
    node = SimpleNamespace(
        name="Imported",
        position=(0.0, 0.0, 0.0),
        vertices=[(0.0, 0.0, 0.0), (4.0, 2.0, 8.0)],
        normals=[],
    )
    model = _Model(node)

    wf._apply_point_transform_to_model(
        model,
        transform_point=lambda point: (
            point[0] * 0.25 + 1.0,
            point[1] * 0.25 - 2.0,
            point[2] * 0.25 + 0.5,
        ),
        transform_direction=lambda direction: direction,
        mark_vertices_world=True,
    )

    assert model._gr_render_bounds == (
        (1.0, -2.0, 0.5),
        (2.0, -1.5, 2.5),
    )
    assert model.bb_min == model._gr_render_bounds[0]
    assert model.bb_max == model._gr_render_bounds[1]
    assert model._gr_bounds_prepared is True
