"""Minimal undo/redo snapshots for destructive mesh edits."""

from __future__ import annotations

from dataclasses import dataclass, field
import copy


_SNAPSHOT_ATTRS = (
    "vertices",
    "normals",
    "tangents",
    "uvs",
    "uvs_lm",
    "uvs_2",
    "uvs_3",
    "faces",
    "face_mats",
    "face_uvs",
    "skin_data",
    "bone_map",
    "texture",
    "lightmap",
    "texture_names",
    "tex_count",
)


@dataclass(slots=True)
class MeshSnapshot:
    mesh: object
    data: dict[str, object]


@dataclass(slots=True)
class MeshHistoryCommand:
    label: str
    before: list[MeshSnapshot]
    after: list[MeshSnapshot]


@dataclass
class MeshHistory:
    limit: int = 100
    undo_stack: list[MeshHistoryCommand] = field(default_factory=list)
    redo_stack: list[MeshHistoryCommand] = field(default_factory=list)

    def snapshot(self, meshes) -> list[MeshSnapshot]:
        return [snapshot_mesh(mesh) for mesh in meshes if mesh is not None]

    def record(self, label: str, before: list[MeshSnapshot], after: list[MeshSnapshot]) -> None:
        if not before and not after:
            return
        self.undo_stack.append(MeshHistoryCommand(label=label, before=before, after=after))
        if len(self.undo_stack) > self.limit:
            del self.undo_stack[0 : len(self.undo_stack) - self.limit]
        self.redo_stack.clear()

    def undo(self) -> bool:
        if not self.undo_stack:
            return False
        command = self.undo_stack.pop()
        for snapshot in command.before:
            restore_snapshot(snapshot)
        self.redo_stack.append(command)
        return True

    def redo(self) -> bool:
        if not self.redo_stack:
            return False
        command = self.redo_stack.pop()
        for snapshot in command.after:
            restore_snapshot(snapshot)
        self.undo_stack.append(command)
        return True


def snapshot_mesh(mesh) -> MeshSnapshot:
    return MeshSnapshot(
        mesh=mesh,
        data={attr: copy.deepcopy(getattr(mesh, attr)) for attr in _SNAPSHOT_ATTRS if hasattr(mesh, attr)},
    )


def restore_snapshot(snapshot: MeshSnapshot) -> None:
    for attr, value in snapshot.data.items():
        setattr(snapshot.mesh, attr, copy.deepcopy(value))
    if hasattr(snapshot.mesh, "compute_bounds"):
        snapshot.mesh.compute_bounds()
