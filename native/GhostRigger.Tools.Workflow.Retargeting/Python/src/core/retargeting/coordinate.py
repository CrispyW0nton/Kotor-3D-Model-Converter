"""Matrix-based coordinate and unit conversion helpers for retargeting."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

import numpy as np

from .source_animation import Transform


def _basis_matrix(value: Iterable[Iterable[float]]) -> np.ndarray:
    matrix = np.asarray(value, dtype=np.float64)
    if matrix.shape != (3, 3):
        raise ValueError(f"Basis matrix must be 3x3, got {matrix.shape}")
    det = float(np.linalg.det(matrix))
    if abs(det) <= 1e-12:
        raise ValueError("Basis matrix is degenerate")
    return matrix


@dataclass(frozen=True)
class BasisConversion:
    """Convert points, rotations, and transforms through explicit bases."""

    source_basis: np.ndarray
    target_basis: np.ndarray
    unit_scale: float = 1.0

    def __post_init__(self) -> None:
        object.__setattr__(self, "source_basis", _basis_matrix(self.source_basis))
        object.__setattr__(self, "target_basis", _basis_matrix(self.target_basis))
        object.__setattr__(self, "unit_scale", float(self.unit_scale))

    @property
    def change_of_basis(self) -> np.ndarray:
        """Matrix that converts source-basis coordinates into target-basis coordinates."""

        return np.linalg.inv(self.target_basis) @ self.source_basis

    def convert_point(self, point: Iterable[float]) -> tuple[float, float, float]:
        values = np.asarray(list(point), dtype=np.float64)[:3]
        converted = self.change_of_basis @ values
        converted *= self.unit_scale
        return tuple(float(value) for value in converted)

    def convert_rotation_matrix(self, rotation: Iterable[Iterable[float]]) -> np.ndarray:
        rot = np.asarray(rotation, dtype=np.float64)[:3, :3]
        basis = self.change_of_basis
        converted = basis @ rot @ np.linalg.inv(basis)
        u, _singular, vh = np.linalg.svd(converted)
        return u @ vh

    def convert_transform(self, transform: Transform) -> Transform:
        matrix = transform.to_matrix()
        out = np.eye(4, dtype=np.float64)
        out[:3, :3] = self.convert_rotation_matrix(matrix[:3, :3])
        out[:3, 3] = np.asarray(self.convert_point(transform.position), dtype=np.float64)
        return Transform.from_matrix(out)


UE_X_FORWARD_Y_RIGHT_Z_UP = "UE_X_FORWARD_Y_RIGHT_Z_UP"
UE_UNIT_SCALE_TO_METERS = 0.01
