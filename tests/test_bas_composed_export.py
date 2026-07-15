"""BAS composed export: a head grafted onto a headless body exports as one model.

The Body Attachment System composes the body and every attached layer (head,
mask, weapons, belt) into a single KotorModel whose hook nodes carry the
layers as real child subtrees.  The main-viewport "Export Composed Model…"
button writes that one model straight through the MDL/OBJ/FBX workers, so a
headless body plus any game head leaves the tool as a single merged file.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")


def _configure_native_python_roots() -> None:
    from scripts.mcp.start_kotormcp_stdio import _python_roots

    for item in reversed(_python_roots(ROOT)):
        value = str(item)
        if value not in sys.path:
            sys.path.insert(0, value)


def _body_with_headhook():
    from src.core.geometry import model_data as md

    root = md.ModelNode(name="pmbam", flags=int(md.NodeFlags.HEADER))
    body = md.ModelNode(
        name="pmbam_body",
        flags=int(md.NodeFlags.HEADER) | int(md.NodeFlags.MESH),
        vertices=[(0.0, 0.0, 0.0), (1.0, 0.0, 0.0), (0.0, 1.0, 0.0)],
        faces=[(0, 1, 2)],
        texture="pmbam01",
    )
    body.parent = root
    headhook = md.ModelNode(name="headhook", flags=int(md.NodeFlags.HEADER))
    headhook.position = (0.0, 0.0, 1.8)
    headhook.parent = root
    root.children.extend([body, headhook])
    return md.KotorModel(name="pmbam", root_node=root)


def _head_model():
    from src.core.geometry import model_data as md

    root = md.ModelNode(name="pmhc01", flags=int(md.NodeFlags.HEADER))
    head = md.ModelNode(
        name="pmhc01_head",
        flags=int(md.NodeFlags.HEADER) | int(md.NodeFlags.MESH),
        vertices=[(0.0, 0.0, 0.0), (0.5, 0.0, 0.0), (0.0, 0.5, 0.0), (0.5, 0.5, 0.0)],
        faces=[(0, 1, 2), (1, 3, 2)],
        texture="pmhc01",
    )
    head.parent = root
    root.children.append(head)
    return md.KotorModel(name="pmhc01", root_node=head and root)


def _node_names(model):
    return {str(getattr(node, "name", "") or "").lower() for node in model.all_nodes()}


def test_head_is_grafted_into_the_composed_model_tree() -> None:
    _configure_native_python_roots()
    from src.systems.bas.preview_composer import build_bas_preview_model

    composed = build_bas_preview_model(
        body_model=_body_with_headhook(),
        attachment_models={"head": _head_model()},
        name="pmbam_bas",
    )
    names = _node_names(composed)
    assert "headhook" in names
    assert "pmhc01_head" in names, "head mesh must be present in the merged tree"
    # The head subtree hangs under the headhook socket, not loose at the root.
    headhook = next(n for n in composed.all_nodes() if str(n.name).lower() == "headhook")
    child_names = {str(getattr(c, "name", "") or "").lower() for c in getattr(headhook, "children", [])}
    assert "pmhc01" in child_names or "pmhc01_head" in child_names


def test_composed_model_exports_as_one_mdl_with_the_head() -> None:
    _configure_native_python_roots()
    from src.core.mdl.mdl_parser import MDLBinaryParser
    from src.core.mdl.mdl_writer import MDLBinaryWriter
    from src.systems.bas.preview_composer import build_bas_preview_model

    composed = build_bas_preview_model(
        body_model=_body_with_headhook(),
        attachment_models={"head": _head_model()},
        name="pmbam_bas",
    )
    mdl_bytes, mdx_bytes = MDLBinaryWriter().write(composed)
    assert mdl_bytes and mdx_bytes
    reloaded = MDLBinaryParser(mdl_bytes, mdx_bytes).parse()
    names = _node_names(reloaded)
    assert "pmbam_body" in names
    assert "pmhc01_head" in names, "the grafted head must survive the single-MDL roundtrip"


def test_composed_model_exports_as_one_obj_with_the_head(tmp_path) -> None:
    _configure_native_python_roots()
    from src.converters.mesh_converter import OBJExporter
    from src.systems.bas.preview_composer import build_bas_preview_model

    composed = build_bas_preview_model(
        body_model=_body_with_headhook(),
        attachment_models={"head": _head_model()},
        name="pmbam_bas",
    )
    obj_path = tmp_path / "pmbam_bas.obj"
    OBJExporter().export(composed, str(obj_path), export_rigging=False)
    text = obj_path.read_text(encoding="utf-8", errors="ignore").lower()
    # The head geometry (4 verts) must appear alongside the body (3 verts):
    # a single OBJ carries both, so at least 7 vertex rows are present.
    assert text.count("\nv ") + text.startswith("v ") >= 7
    assert "pmhc01_head" in text or "pmhc01" in text


def test_export_button_and_handler_are_wired() -> None:
    _configure_native_python_roots()
    panel = (ROOT / "native/GhostRigger.Core.GUI.Display/Python/src/gui/panels/qt_body_attachment_panel.py").read_text(encoding="utf-8")
    assert "exportComposedRequested" in panel
    assert "Export Composed Model" in panel
    layout = (ROOT / "native/GhostRigger.Core.GUI.Display/Python/src/gui/windows/application_core/shared/main_layout.py").read_text(encoding="utf-8")
    assert "exportComposedRequested.connect(self._handle_bas_export_composed_requested)" in layout
    workflow = (ROOT / "native/GhostRigger.Core.GUI.Display/Python/src/gui/windows/application_core/shared/bas_workflow.py").read_text(encoding="utf-8")
    assert "_handle_bas_export_composed_requested" in workflow
    # Tools mirrors must match byte-for-byte.
    for rel in (
        "gui/panels/qt_body_attachment_panel.py",
        "gui/windows/application_core/shared/main_layout.py",
        "gui/windows/application_core/shared/bas_workflow.py",
    ):
        gui = (ROOT / "native/GhostRigger.Core.GUI.Display/Python/src" / rel).read_bytes()
        tools = (ROOT / "native/GhostRigger.Core.Tools/Python/src" / rel).read_bytes()
        assert gui == tools, f"mirror drift: {rel}"
