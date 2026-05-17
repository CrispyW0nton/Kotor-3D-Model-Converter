from __future__ import annotations

import numpy as np

from src.gui import accel


def _draw_edge_sample(*, clamp_s: bool) -> tuple[int, int, int, int]:
    buf = np.zeros((8, 8, 4), dtype=np.uint8)
    tex = np.zeros((1, 2, 4), dtype=np.uint8)
    tex[0, 0] = (255, 0, 0, 255)
    tex[0, 1] = (0, 255, 0, 255)

    accel.rasterize_triangle(
        buf,
        tex,
        1,
        1,
        6,
        1,
        1,
        6,
        1.0,
        0.5,
        1.0,
        0.5,
        1.0,
        0.5,
        255,
        255,
        255,
        clamp_s=clamp_s,
    )
    return tuple(int(c) for c in buf[2, 2])


def test_accel_rasterizer_clamps_u_edge_when_requested() -> None:
    assert _draw_edge_sample(clamp_s=False)[:3] == (255, 0, 0)
    assert _draw_edge_sample(clamp_s=True)[:3] == (0, 255, 0)
