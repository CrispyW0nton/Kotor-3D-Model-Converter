import os, sys

ROOT = "C:/Users/NewAdmin/Documents/GDeveloper/Workspaces/Kotor-3D-Model-Converter-qt/native"
for sub in (
    "GhostRigger.Core.Math/Python",
    "GhostRigger.Core.Workflow/Python",
    "GhostRigger.Core.Scene/Python",
):
    p = os.path.join(ROOT, sub)
    if p not in sys.path:
        sys.path.insert(0, p)

from src.core.characters import headless_body_workflow as wf


class BoneNode:
    """Skeleton bone — has a world position, no mesh."""
    def __init__(self, name, pos):
        self.name = name
        self.position = tuple(float(c) for c in pos)
        self.vertices = []  # not a mesh
        self.children = []


class MeshNode:
    """Imported mesh — vertices/faces, receives skin_data."""
    def __init__(self, vertices, faces, bone_map=None):
        self.name = "body_mesh"
        self.vertices = vertices
        self.faces = faces
        self.bone_map = bone_map or []
        self.skin_data = []
        self.bone_weights = []
        self.bone_indices = []
        self.children = []


class FakeModel:
    def __init__(self, nodes):
        self._nodes = nodes
    def all_nodes(self):
        return list(self._nodes)


# Hand-like skeleton: wrist -> knuckle -> fingertip
bones = [
    BoneNode("hand",    (0.0, 0.0, 0.0)),
    BoneNode("finger1", (1.0, 0.0, 0.0)),
    BoneNode("finger2", (2.0, 0.0, 0.0)),
]

# A thin surface strip along the finger: x in {0,.5,1,1.5,2}, two y-rows.
verts, faces = [], []
rows = (-0.1, 0.1)
xs = (0.0, 0.5, 1.0, 1.5, 2.0)
idx = {}
k = 0
for yi, y in enumerate(rows):
    for xi, x in enumerate(xs):
        idx[(xi, yi)] = k
        verts.append((x, y, 0.0))
        k += 1
for yi in range(len(rows) - 1):
    for xi in range(len(xs) - 1):
        a, b = idx[(xi, yi)], idx[(xi + 1, yi)]
        c, d = idx[(xi, yi + 1)], idx[(xi + 1, yi + 1)]
        faces.append((a, b, d))
        faces.append((a, d, c))

mesh = MeshNode(verts, faces, bone_map=["hand", "finger1", "finger2"])
model = FakeModel(bones + [mesh])

report = wf._compute_heat_diffusion_skin_weights(
    model,
    max_influence_distance=10.0,
    diffusion_iterations=4,
    falloff=2.0,
    max_bones_per_vertex=4,
)
print("REPORT:", report)

assert report["ok"], report
assert report["method"] == "heat_diffusion"
assert report["vertices_skinned"] == len(verts), (report, len(verts))
assert report["mesh_count"] == 1

# Verify the weight contract on every vertex row.
slot_ok = True
sum_ok = True
cap_ok = True
for vi, vsd in enumerate(mesh.skin_data):
    infl = vsd.influences
    s = sum(bw.weight for bw in infl)
    if abs(s - 1.0) > 1e-5:
        sum_ok = False
        print(f"  vertex {vi} sums to {s} (NOT 1.0): {infl}")
    if len(infl) > 4:
        cap_ok = False
    for bw in infl:
        if not (0 <= bw.bone_index < len(mesh.bone_map)):
            slot_ok = False
    # cross-check derived arrays
    assert [bw.weight for bw in infl] == mesh.bone_weights[vi]
    assert [bw.bone_index for bw in infl] == mesh.bone_indices[vi]

print(f"rows={len(mesh.skin_data)} sum_ok={sum_ok} cap<=4={cap_ok} slot_in_range={slot_ok}")
assert sum_ok and cap_ok and slot_ok

# Anatomical sanity: wrist-end vertex (x=0) should favour "hand",
# fingertip vertex (x=2) should favour "finger2".
def dom(vsd):
    return max(vsd.influences, key=lambda bw: bw.weight).bone_index

wrist_vi = idx[(0, 0)]
tip_vi = idx[(len(xs) - 1, 0)]
print("wrist vert dominant slot:", dom(mesh.skin_data[wrist_vi]), "(hand=0)")
print("tip vert dominant slot:  ", dom(mesh.skin_data[tip_vi]), "(finger2=2)")
assert dom(mesh.skin_data[wrist_vi]) == 0, "wrist should favour hand"
assert dom(mesh.skin_data[tip_vi]) == 2, "tip should favour finger2"

print("INTEGRATION_OK")
