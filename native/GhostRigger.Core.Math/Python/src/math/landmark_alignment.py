'''Landmark-based rigid alignment using the Kabsch algorithm.

Given a set of source landmarks (from the imported mesh) and corresponding
target landmarks (from the donor skeleton), compute the optimal rotation
matrix that minimizes RMSD between the two point sets.

This replaces the bounding-box-extent heuristic in the Character Builder
auto-fit pipeline with a mathematically rigorous approach.

The module is intentionally NumPy-only and free of any GhostRigger/Qt
dependencies so it can be imported as ``src.math.landmark_alignment`` from
the workflow layer and unit-tested in isolation.
'''

from __future__ import annotations
import math
import numpy as np


def kabsch_optimal_rotation(
    source_points: np.ndarray,  # (N, 3)
    target_points: np.ndarray,  # (N, 3)
) -> np.ndarray:
    '''Compute optimal rotation matrix via SVD.

    Returns a 3x3 rotation matrix R such that R @ source_centered ≈ target_centered.
    Uses the Kabsch algorithm: compute H = source_centered.T @ target_centered,
    then R = V @ U.T from SVD(H), with reflection correction.
    '''
    assert source_points.shape == target_points.shape
    assert source_points.shape[1] == 3

    source_centroid = source_points.mean(axis=0)
    target_centroid = target_points.mean(axis=0)

    source_centered = source_points - source_centroid
    target_centered = target_points - target_centroid

    # Cross-covariance matrix
    H = source_centered.T @ target_centered

    U, S, Vt = np.linalg.svd(H)

    # Correct for reflection
    d = np.sign(np.linalg.det(Vt.T @ U.T))
    D = np.diag([1.0, 1.0, d])
    R = Vt.T @ D @ U.T

    return R


def compute_rigid_transform(
    source_points: np.ndarray,
    target_points: np.ndarray,
) -> tuple[np.ndarray, np.ndarray, float]:
    '''Compute full rigid transform: rotation, translation, uniform scale.

    Returns (R, t, scale) such that scale * R @ source + t ≈ target.
    '''
    source_centroid = source_points.mean(axis=0)
    target_centroid = target_points.mean(axis=0)

    source_centered = source_points - source_centroid
    target_centered = target_points - target_centroid

    R = kabsch_optimal_rotation(source_points, target_points)

    # Uniform scale (ratio of RMS deviations)
    source_rms = np.sqrt(np.mean(np.sum(source_centered**2, axis=1)))
    target_rms = np.sqrt(np.mean(np.sum(target_centered**2, axis=1)))
    scale = float(target_rms / source_rms) if source_rms > 1e-9 else 1.0

    t = target_centroid - scale * R @ source_centroid

    return R, t, scale


def pca_principal_axes(vertices: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    '''Compute the 3 principal axes of a vertex cloud via PCA.

    Returns (eigenvalues, eigenvectors) sorted by descending eigenvalue.
    The first eigenvector is the direction of maximum variance.
    '''
    centroid = vertices.mean(axis=0)
    centered = vertices - centroid
    cov = centered.T @ centered / max(1, len(centered) - 1)
    eigenvalues, eigenvectors = np.linalg.eigh(cov)
    # eigh returns ascending; flip to descending
    eigenvalues = eigenvalues[::-1]
    eigenvectors = eigenvectors[:, ::-1]
    return eigenvalues, eigenvectors


def extract_mesh_landmarks(vertices: np.ndarray) -> dict[str, np.ndarray]:
    '''Extract geometric landmarks from a mesh vertex cloud.

    Returns a dict with:
    - 'centroid': the center of mass
    - 'top': the highest vertex (max Z)
    - 'bottom': the lowest vertex (min Z)
    - 'left': the leftmost vertex (min X)
    - 'right': the rightmost vertex (max X)
    - 'front': the frontmost vertex (max Y)
    - 'back': the backmost vertex (min Y)
    '''
    centroid = vertices.mean(axis=0)
    top_idx = np.argmax(vertices[:, 2])
    bottom_idx = np.argmin(vertices[:, 2])
    left_idx = np.argmin(vertices[:, 0])
    right_idx = np.argmax(vertices[:, 0])
    front_idx = np.argmax(vertices[:, 1])
    back_idx = np.argmin(vertices[:, 1])

    return {
        'centroid': centroid,
        'top': vertices[top_idx],
        'bottom': vertices[bottom_idx],
        'left': vertices[left_idx],
        'right': vertices[right_idx],
        'front': vertices[front_idx],
        'back': vertices[back_idx],
    }


def extract_bone_landmarks(bone_positions: dict[str, np.ndarray]) -> dict[str, np.ndarray]:
    '''Extract landmarks from a skeleton's bone positions.

    Takes a dict mapping bone/node names to 3D positions and returns
    the same landmark structure as extract_mesh_landmarks so they can
    be directly compared.
    '''
    positions = np.array(list(bone_positions.values()))
    centroid = positions.mean(axis=0)
    top_idx = np.argmax(positions[:, 2])
    bottom_idx = np.argmin(positions[:, 2])
    left_idx = np.argmin(positions[:, 0])
    right_idx = np.argmax(positions[:, 0])
    front_idx = np.argmax(positions[:, 1])
    back_idx = np.argmin(positions[:, 1])

    return {
        'centroid': centroid,
        'top': positions[top_idx],
        'bottom': positions[bottom_idx],
        'left': positions[left_idx],
        'right': positions[right_idx],
        'front': positions[front_idx],
        'back': positions[back_idx],
    }


def align_mesh_to_skeleton(
    mesh_vertices: np.ndarray,
    bone_positions: dict[str, np.ndarray],
) -> dict:
    '''Compute the optimal rigid transform to fit a mesh onto a skeleton.

    Returns a dict with:
    - 'rotation_matrix': 3x3 rotation matrix (row-major tuples for GhostRigger)
    - 'translation': (x, y, z) translation
    - 'scale': uniform scale factor
    - 'rmsd': root-mean-square deviation after alignment
    - 'method': 'landmark_kabsch' or 'pca_fallback'
    - 'source_landmarks': the mesh landmarks used
    - 'target_landmarks': the bone landmarks used
    '''
    mesh_landmarks = extract_mesh_landmarks(mesh_vertices)
    bone_landmarks = extract_bone_landmarks(bone_positions)

    # Build corresponding point arrays using extrema landmarks
    landmark_keys = ['top', 'bottom', 'left', 'right', 'front', 'back', 'centroid']
    source_pts = np.array([mesh_landmarks[k] for k in landmark_keys])
    target_pts = np.array([bone_landmarks[k] for k in landmark_keys])

    R, t, scale = compute_rigid_transform(source_pts, target_pts)

    # Compute RMSD
    transformed = scale * (R @ source_pts.T).T + t
    rmsd = float(np.sqrt(np.mean(np.sum((transformed - target_pts)**2, axis=1))))

    # Convert rotation to GhostRigger row-major tuple format
    rotation_matrix = (
        (float(R[0, 0]), float(R[0, 1]), float(R[0, 2])),
        (float(R[1, 0]), float(R[1, 1]), float(R[1, 2])),
        (float(R[2, 0]), float(R[2, 1]), float(R[2, 2])),
    )

    return {
        'rotation_matrix': rotation_matrix,
        'translation': (float(t[0]), float(t[1]), float(t[2])),
        'scale': float(scale),
        'rmsd': rmsd,
        'method': 'landmark_kabsch',
        'source_landmarks': mesh_landmarks,
        'target_landmarks': bone_landmarks,
    }
