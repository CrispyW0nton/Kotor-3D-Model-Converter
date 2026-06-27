import numpy as np
import heat_diffusion_skinning as hd

# Simple unit: two-bone skeleton, a thin mesh spanning them.
verts = np.array([[0, 0, 0], [1, 0, 0], [2, 0, 0], [3, 0, 0]], dtype=float)
faces = [(0, 1), (1, 2), (2, 3)]  # degenerate 'faces' to exercise adjacency
bones = {"root": np.array([0, 0, 0.0]), "tip": np.array([3, 0, 0.0])}
w = hd.compute_heat_diffusion_weights(
    verts, faces, bones, max_influence_distance=10.0, diffusion_iterations=3
)
assert len(w) == 4, w
for vi, row in w.items():
    s = sum(row.values())
    assert abs(s - 1.0) < 1e-6, (vi, s)
print("root-end v0 weights:", sorted(w[0].items(), key=lambda x: -x[1]))
print("tip-end v3 weights:", sorted(w[3].items(), key=lambda x: -x[1]))

seg = hd.segment_mesh_by_bones(verts, bones)
print("segment keys:", sorted(seg.keys()))
print("adjacency:", hd.build_adjacency_graph(verts, faces))

# Triangle mesh with 5 bones, ensure cap<=4 and all verts covered.
verts2 = np.array(
    [[0, 0, 0], [1, 0, 0], [0, 1, 0], [1, 1, 0], [2, 0, 0], [2, 1, 0]],
    dtype=float,
)
faces2 = [(0, 1, 2), (1, 3, 2), (1, 4, 3), (4, 5, 3)]
bones2 = {
    "b0": np.array([0, 0, 0.0]),
    "b1": np.array([1, 0, 0.0]),
    "b2": np.array([0, 1, 0.0]),
    "b3": np.array([1, 1, 0.0]),
    "b4": np.array([2, 0.5, 0.0]),
}
w2 = hd.compute_heat_diffusion_weights(
    verts2, faces2, bones2,
    max_influence_distance=10.0, diffusion_iterations=4, max_bones_per_vertex=4,
)
for vi, row in w2.items():
    assert len(row) <= 4, (vi, row)
    assert abs(sum(row.values()) - 1.0) < 1e-6, (vi, sum(row.values()))
print("SMOKE_OK")

# Edge case: point cloud (no faces) — seeded verts must keep their weights.
verts3 = np.array([[0, 0, 0], [3, 0, 0]], dtype=float)
bones3 = {"root": np.array([0, 0, 0.0]), "tip": np.array([3, 0, 0.0])}
w3 = hd.compute_heat_diffusion_weights(
    verts3, [], bones3, max_influence_distance=10.0, diffusion_iterations=3
)
assert len(w3) == 2, w3
assert abs(sum(w3[0].values()) - 1.0) < 1e-6, w3[0]
assert w3[0].get("root", 0) > w3[0].get("tip", 0), w3[0]
assert w3[1].get("tip", 0) > w3[1].get("root", 0), w3[1]
print("POINTCLOUD_OK")
