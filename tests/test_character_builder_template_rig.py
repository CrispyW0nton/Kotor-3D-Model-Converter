from __future__ import annotations

import inspect
import math
from types import SimpleNamespace

from src.core.characters.character_builder import apply_template_rig
from src.core.characters.character_rig_state import get_character_rig_state
from src.core.animation.animation_engine import AnimPose, NodePose
from src.core.animation.gpu_skinning import MatrixPaletteUploader
from src.core.geometry.model_data import (
    BoneWeight,
    CharacterScene,
    KotorModel,
    ModelNode,
    NodeFlags,
    PartSlot,
    VertexSkinData,
)
from src.core.diagnostics.validation_service import ValidationService
from src.gui.qt_lib.panels.qt_character_builder_panel import QtCharacterBuilderWindow
from src.systems.bas.preview_composer import build_bas_preview_model
from src.gui.viewports.viewport_core.widgets.drag_interactions import (
    ViewportDragInteractionsMixin,
)


def _node(name: str, flags: int = int(NodeFlags.HEADER), parent: ModelNode | None = None) -> ModelNode:
    node = ModelNode(name=name, flags=flags)
    if parent is not None:
        node.parent = parent
        parent.children.append(node)
    return node


def test_character_builder_preview_uses_bas_socket_layers_for_attachments() -> None:
    body_root = _node("BodyRoot")
    headhook = _node("headhook", parent=body_root)
    rhand = _node("rhand", parent=body_root)
    body_skin = _node(
        "body_skin",
        flags=int(NodeFlags.HEADER | NodeFlags.MESH | NodeFlags.SKIN),
        parent=body_root,
    )
    body_skin.bone_map = ["BodyRoot", "headhook", "rhand"]
    body = KotorModel(name="Body", root_node=body_root)

    head_root = _node("HeadRoot")
    head_skin = _node(
        "head_skin",
        flags=int(NodeFlags.HEADER | NodeFlags.MESH | NodeFlags.SKIN),
        parent=head_root,
    )
    head_skin.bone_map = ["head_g"]
    head = KotorModel(name="PMHA01", root_node=head_root)

    weapon_root = _node("WeaponRoot")
    weapon = KotorModel(name="w_lghtsbr_001", root_node=weapon_root)

    preview = build_bas_preview_model(
        body_model=body,
        attachment_models={"head": head, "right_weapon": weapon},
        attachment_transforms={"right_weapon": {"position": [0.0, 0.0, 0.0]}},
        name="Body BAS Preview",
    )

    preview_headhook = preview.find_node("headhook")
    preview_rhand = preview.find_node("rhand")
    assert preview_headhook is not None
    assert preview_rhand is not None
    assert preview_headhook.children[-1].name == "HeadRoot"
    assert preview_rhand.children[-1].name == "WeaponRoot"
    assert preview_headhook.children[-1]._gr_bas_attachment_root is True
    assert preview_headhook.children[-1]._gr_bas_socket_name == "headhook"
    assert preview_rhand.children[-1]._gr_bas_socket_name == "rhand"
    assert preview_headhook.children[-1].children[0]._gr_bas_attachment_layer is True
    assert preview.find_node("body_skin").bone_map == ["BodyRoot", "headhook", "rhand"]


def test_character_builder_legacy_acurig_slots_are_off_by_default() -> None:
    init_source = inspect.getsource(QtCharacterBuilderWindow.__init__)
    place_source = inspect.getsource(QtCharacterBuilderWindow._on_place_body_guides_requested)
    generate_source = inspect.getsource(QtCharacterBuilderWindow._on_generate_skeleton_requested)
    hand_source = inspect.getsource(QtCharacterBuilderWindow._on_place_hand_guides_requested)
    mask_source = inspect.getsource(QtCharacterBuilderWindow._on_hand_mask_changed)

    assert "_legacy_acurig_enabled = False" in init_source
    assert hasattr(QtCharacterBuilderWindow, "set_legacy_acurig_enabled")
    assert "_require_legacy_acurig_enabled" in place_source
    assert "_require_legacy_acurig_enabled" in generate_source
    assert "_require_legacy_acurig_enabled" in hand_source
    assert "_require_legacy_acurig_enabled" in mask_source


def test_character_builder_inspector_labels_legacy_acurig_controls() -> None:
    from src.gui.qt_lib.panels.qt_inspector_panel import QtInspectorPanel

    source = inspect.getsource(QtInspectorPanel._populate_rig_page)

    assert "Legacy / Experimental AcuRig" in source
    assert "Legacy: Place Body Guides" in source
    assert "Legacy: Create New Skeleton" in source
    assert "Legacy / Experimental Hand AcuRig" in source
    assert "Legacy: Rebuild Hand Guides" in source


def test_character_builder_gizmo_routes_promoted_root_to_model_fit_drag() -> None:
    root = SimpleNamespace(name="bendak")

    class _FakeCharacterBuilderDrag(ViewportDragInteractionsMixin):
        def __init__(self):
            self.model = SimpleNamespace(root_node=root)
            self._mesh_transform_promotes_to_model_root = True

        def _is_selected_model_root(self, node) -> bool:
            return node is root

    view = _FakeCharacterBuilderDrag()

    assert view._should_use_model_fit_gizmo_drag(root) is True
    view._mesh_transform_promotes_to_model_root = False
    assert view._should_use_model_fit_gizmo_drag(root) is False


def test_character_builder_overlay_setters_do_not_require_widget_redraw() -> None:
    from src.core.camera.arcball_camera import ArcBallCamera
    from src.core.rendering.frame_core.renderer import FrameRenderer

    renderer = FrameRenderer(ArcBallCamera())

    renderer.set_acurig_guides({})
    renderer.set_character_fit_overlay({"source": {"origin": [0.0, 0.0, 0.0]}})

    assert getattr(renderer, "_acurig_guides_overlay") == {}
    assert getattr(renderer, "_character_fit_overlay") is not None


def test_apply_template_rig_strips_imported_armature_and_clears_old_skin() -> None:
    src_root = _node("Bendak_UE")
    src_root.position = (10.0, 0.0, 0.0)
    ue_pelvis = _node("pelvis", parent=src_root)
    ue_pelvis.position = (0.0, 2.0, 0.0)
    ue_spine = _node("spine_01", parent=ue_pelvis)
    mesh = _node(
        "Bendak",
        flags=int(NodeFlags.HEADER | NodeFlags.MESH | NodeFlags.SKIN),
        parent=ue_spine,
    )
    mesh.position = (0.0, 0.0, 3.0)
    mesh.vertices = [(1.0, 0.0, 0.0)]
    mesh.normals = [(0.0, 0.0, 1.0)]
    mesh.faces = [(0, 0, 0)]
    mesh.bone_map = ["pelvis"]
    mesh.bone_map_floats = [0.0]
    mesh.skin_data = [VertexSkinData([BoneWeight(0, 1.0)])]
    mesh.qbone_list = [(0.0, 0.0, 0.0, 1.0)]
    mesh.tbone_list = [(0.0, 0.0, 0.0)]
    mesh.children.append(_node("UE_Mesh_Attachment"))
    mesh.children[-1].parent = mesh
    mesh_model = KotorModel(name="bendak", root_node=src_root)

    kotor_root = _node("N_Mandalorian")
    _node("rootdummy", parent=kotor_root)
    _node("template_body_mesh", flags=int(NodeFlags.HEADER | NodeFlags.MESH), parent=kotor_root)
    template = KotorModel(name="n_mandalorian", root_node=kotor_root, supermodel="S_Female02")
    template._gr_source_resref = "n_mandalorian"
    template._gr_source_game = "K1"
    template._gr_source_layer = "game_library"

    result = apply_template_rig(mesh_model, template, game="K1", scale_mode="manual")

    assert result["ok"] is True
    rigged = result["model"]
    names = [node.name for node in rigged.all_nodes()]
    assert names[0] == "N_Mandalorian"
    assert "rootdummy" in names
    assert "Bendak" in names
    assert "pelvis" not in names
    assert "spine_01" not in names
    assert "UE_Mesh_Attachment" not in names
    assert "template_body_mesh" not in names

    rigged_mesh = rigged.find_node("Bendak")
    assert rigged_mesh is not None
    assert rigged_mesh.parent is rigged.root_node
    assert rigged_mesh.children == []
    assert rigged_mesh.is_mesh is True
    assert rigged_mesh.is_skin is True
    assert rigged_mesh.bone_map == ["rootdummy"]
    assert rigged_mesh.bone_map_floats
    assert len(rigged_mesh.skin_data) == len(rigged_mesh.vertices)
    assert len(rigged_mesh.skin_data[0].influences) == 1
    assert rigged_mesh.skin_data[0].influences[0].bone_index == 0
    assert math.isclose(rigged_mesh.skin_data[0].influences[0].weight, 1.0)
    assert len(rigged_mesh.qbone_list) == len(rigged_mesh.bone_map)
    assert len(rigged_mesh.tbone_list) == len(rigged_mesh.bone_map)
    skin_binding = rigged.metadata["character_builder_bind"]["skin_binding"]
    assert skin_binding["weighting_method"] == "nearest_kotor_bone_segment"
    assert skin_binding["quality_stage"] == "fallback_first_pass"
    assert skin_binding["donor_weight_transfer"] is False
    assert skin_binding["mesh_reports"][0]["mesh_name"] == "Bendak"
    assert skin_binding["mesh_reports"][0]["weighted_vertices"] == 1
    assert skin_binding["mesh_reports"][0]["bone_map_count"] == 1
    assert rigged_mesh._gr_skin_binding_report == skin_binding["mesh_reports"][0]
    assert rigged_mesh._gr_bound_to_kotor_skeleton is True
    assert rigged_mesh._gr_kotor_skeleton_root == "N_Mandalorian"
    assert rigged_mesh.position == (0.0, 0.0, 0.0)
    assert rigged_mesh.rotation == (0.0, 0.0, 0.0, 1.0)
    assert rigged_mesh.vertices[0] == (11.0, 2.0, 3.0)
    bind = rigged.metadata["character_builder_bind"]
    assert bind["status"] == "bound_to_native_kotor_skeleton"
    assert bind["native_base"] == {
        "source_resref": "n_mandalorian",
        "model_name": "n_mandalorian",
        "game": "K1",
        "supermodel": "S_Female02",
        "dag_authority": "native_kotor_base",
        "replaced_render_payload_nodes": [
            {
                "name": "template_body_mesh",
                "path": ["N_Mandalorian", "template_body_mesh"],
                "is_mesh": True,
                "is_skin": False,
                "vertex_count": 0,
                "face_count": 0,
                "texture": "",
                "replacement": "imported_mesh_payload",
            }
        ],
        "replaced_render_payload_count": 1,
    }
    assert bind["imported_payload"]["model_name"] == "bendak"
    assert bind["imported_payload"]["mesh_role"] == "payload_guest"
    assert bind["imported_payload"]["mesh_names"] == ["Bendak"]
    state = get_character_rig_state(rigged)
    assert state is not None
    assert state.native_base_resref == "n_mandalorian"
    assert state.native_base_model_name == "n_mandalorian"
    assert state.native_base_game == "K1"
    assert state.imported_payload_name == "bendak"
    assert state.payload_mesh_names == ("Bendak",)
    assert rigged._gr_character_builder_bind_complete is True
    assert "KOTOR skeleton built" in result["message"]
    assert result["skinned_meshes"] == 1
    assert result["weighted_vertices"] == 1
    assert result["removed_import_nodes"] >= 3
    assert result["replaced_native_render_nodes"] == [
        {
            "name": "template_body_mesh",
            "path": ["N_Mandalorian", "template_body_mesh"],
            "is_mesh": True,
            "is_skin": False,
            "vertex_count": 0,
            "face_count": 0,
            "texture": "",
            "replacement": "imported_mesh_payload",
        }
    ]


def test_apply_template_rig_does_not_rebake_already_fitted_external_vertices() -> None:
    src_root = _node("Bendak_UE")
    src_root.position = (10.0, 0.0, 0.0)
    armature_node = _node("Armature", parent=src_root)
    armature_node.position = (0.0, 4.0, 0.0)
    mesh = _node("BendakFit", flags=int(NodeFlags.HEADER | NodeFlags.MESH), parent=armature_node)
    mesh.position = (0.0, 0.0, 7.0)
    mesh.vertices = [(5.0, 0.25, 1.5)]
    mesh.normals = [(0.0, 0.0, 1.0)]
    mesh.faces = [(0, 0, 0)]
    mesh._gr_vertices_in_kotor_world = True
    mesh_model = KotorModel(name="bendak", root_node=src_root)

    kotor_root = _node("N_Mandalorian")
    rootdummy = _node("rootdummy", parent=kotor_root)
    rootdummy.position = (0.0, 0.0, 0.9)
    template = KotorModel(name="n_mandalorian", root_node=kotor_root, supermodel="S_Female02")

    result = apply_template_rig(mesh_model, template, game="K1", scale_mode="manual")

    assert result["ok"] is True
    rigged_mesh = result["model"].find_node("BendakFit")
    assert rigged_mesh is not None
    assert rigged_mesh.vertices == [(5.0, 0.25, 1.5)]
    assert rigged_mesh.position == (0.0, 0.0, 0.0)
    assert rigged_mesh._gr_vertices_in_kotor_world is True


def test_apply_template_rig_generated_skin_bind_palette_survives_kotor_parent_flip() -> None:
    src_root = _node("Bendak_UE")
    mesh = _node("BendakFit", flags=int(NodeFlags.HEADER | NodeFlags.MESH), parent=src_root)
    mesh.vertices = [(2.0, 0.0, 0.0)]
    mesh.faces = [(0, 0, 0)]
    mesh._gr_vertices_in_kotor_world = True
    mesh_model = KotorModel(name="bendak", root_node=src_root)

    kotor_root = _node("N_Mandalorian")
    kotor_root.rotation = (0.0, 0.0, 1.0, 0.0)
    rootdummy = _node("rootdummy", parent=kotor_root)
    rootdummy.position = (1.0, 0.0, 0.0)
    template = KotorModel(name="n_mandalorian", root_node=kotor_root, supermodel="S_Male02")

    result = apply_template_rig(mesh_model, template, game="K1", scale_mode="manual")

    assert result["ok"] is True
    rigged_mesh = result["model"].find_node("BendakFit")
    assert rigged_mesh is not None
    assert rigged_mesh.bone_map == ["rootdummy"]

    uploader = MatrixPaletteUploader()
    uploader.build_inverse_bind_pose(result["model"])
    palette = uploader.compute_skin_node_palette(rigged_mesh, AnimPose(time=0.0))

    assert len(palette) == 1
    identity_col_major = [
        1.0, 0.0, 0.0, 0.0,
        0.0, 1.0, 0.0, 0.0,
        0.0, 0.0, 1.0, 0.0,
        0.0, 0.0, 0.0, 1.0,
    ]
    for actual, expected in zip(palette[0].flat_col, identity_col_major):
        assert math.isclose(actual, expected, abs_tol=1.0e-6)


def test_apply_template_rig_live_palette_uses_animation_base_pose_for_imported_skin() -> None:
    src_root = _node("Bendak_UE")
    mesh = _node("BendakFit", flags=int(NodeFlags.HEADER | NodeFlags.MESH), parent=src_root)
    mesh.vertices = [(2.0, 0.0, 0.0)]
    mesh.faces = [(0, 0, 0)]
    mesh._gr_vertices_in_kotor_world = True
    mesh_model = KotorModel(name="bendak", root_node=src_root)

    kotor_root = _node("N_Mandalorian")
    rootdummy = _node("rootdummy", parent=kotor_root)
    template = KotorModel(name="n_mandalorian", root_node=kotor_root, supermodel="S_Male02")

    result = apply_template_rig(mesh_model, template, game="K1", scale_mode="manual")

    assert result["ok"] is True
    rigged_mesh = result["model"].find_node("BendakFit")
    assert rigged_mesh is not None
    rigged_mesh.qbone_list = []
    rigged_mesh.tbone_list = []
    assert rigged_mesh.qbone_list == []
    assert rigged_mesh.tbone_list == []

    base_pose = AnimPose(
        time=0.0,
        nodes={
            "rootdummy": NodePose(
                name="rootdummy",
                position=(0.5, 0.0, 0.0),
            )
        },
    )
    current_pose = AnimPose(
        time=0.5,
        nodes={
            "rootdummy": NodePose(
                name="rootdummy",
                position=(0.5, 0.0, 0.0),
            )
        },
    )
    uploader = MatrixPaletteUploader()
    uploader.build_inverse_bind_pose(result["model"])
    palette = uploader.compute_skin_node_palette(
        rigged_mesh,
        current_pose,
        anim_base_pose=base_pose,
    )

    identity_col_major = [
        1.0, 0.0, 0.0, 0.0,
        0.0, 1.0, 0.0, 0.0,
        0.0, 0.0, 1.0, 0.0,
        0.0, 0.0, 0.0, 1.0,
    ]
    for actual, expected in zip(palette[0].flat_col, identity_col_major):
        assert math.isclose(actual, expected, abs_tol=1.0e-6)


def test_apply_template_rig_does_not_scale_native_template_in_manual_mode() -> None:
    src_root = _node("import_root")
    mesh = _node("body_mesh", flags=int(NodeFlags.HEADER | NodeFlags.MESH), parent=src_root)
    mesh.vertices = [(0.0, 0.0, 0.0)]
    mesh.faces = [(0, 0, 0)]
    mesh_model = KotorModel(name="body", root_node=src_root)

    kotor_root = _node("AdjustedSkeleton")
    hand = _node("rhand", parent=kotor_root)
    hand.position = (1.25, 0.5, 0.75)
    template = KotorModel(name="adjusted", root_node=kotor_root)

    result = apply_template_rig(mesh_model, template, game="K1", scale_mode="manual", scale_factor=2.0)

    assert result["ok"] is True
    rigged_hand = result["model"].find_node("rhand")
    assert rigged_hand is not None
    assert math.isclose(rigged_hand.position[0], 1.25)
    assert math.isclose(rigged_hand.position[1], 0.5)
    assert math.isclose(rigged_hand.position[2], 0.75)
    assert result["scale"] == 1.0
    assert result["requested_scale"] == 2.0
    assert any("ignored" in warning for warning in result["warnings"])
    assert (
        result["model"].metadata["character_builder_bind"]["skeleton_scale_applied"]
        == 1.0
    )


def test_apply_template_rig_transfers_native_template_donor_weights_by_nearest_vertex() -> None:
    src_root = _node("import_root")
    mesh = _node("body_mesh", flags=int(NodeFlags.HEADER | NodeFlags.MESH), parent=src_root)
    mesh.vertices = [(-1.1, 0.0, 0.0), (1.1, 0.0, 0.0)]
    mesh.faces = [(0, 1, 1)]
    mesh_model = KotorModel(name="body", root_node=src_root)

    kotor_root = _node("NativeRoot")
    _node("left_g", parent=kotor_root)
    _node("right_g", parent=kotor_root)
    donor = _node(
        "NativeTorso",
        flags=int(NodeFlags.HEADER | NodeFlags.MESH | NodeFlags.SKIN),
        parent=kotor_root,
    )
    donor.vertices = [(-1.0, 0.0, 0.0), (1.0, 0.0, 0.0)]
    donor.faces = [(0, 1, 1)]
    donor.bone_map = ["left_g", "right_g"]
    donor.skin_data = [
        VertexSkinData([BoneWeight(0, 1.0)]),
        VertexSkinData([BoneWeight(1, 1.0)]),
    ]
    template = KotorModel(name="native_template", root_node=kotor_root, supermodel="S_Female02")

    result = apply_template_rig(mesh_model, template, game="K1", scale_mode="manual")

    assert result["ok"] is True
    rigged_mesh = result["model"].find_node("body_mesh")
    assert rigged_mesh is not None
    left_index = rigged_mesh.bone_map.index("left_g")
    right_index = rigged_mesh.bone_map.index("right_g")
    assert rigged_mesh.skin_data[0].influences[0].bone_index == left_index
    assert math.isclose(rigged_mesh.skin_data[0].influences[0].weight, 1.0)
    assert rigged_mesh.skin_data[1].influences[0].bone_index == right_index
    assert math.isclose(rigged_mesh.skin_data[1].influences[0].weight, 1.0)
    skin_binding = result["model"].metadata["character_builder_bind"]["skin_binding"]
    assert skin_binding["weighting_method"] == "native_template_nearest_vertex_donor"
    assert skin_binding["quality_stage"] == "donor_transfer_first_pass"
    assert skin_binding["donor_weight_transfer"] is True
    assert skin_binding["mesh_reports"][0]["donor_vertices"] == 2
    assert skin_binding["mesh_reports"][0]["fallback_vertices"] == 0
    assert skin_binding["mesh_reports"][0]["donor_vertex_count"] == 2


def test_apply_template_rig_remaps_imported_source_skin_weights_to_kotor_bones() -> None:
    src_root = _node("import_root")
    mesh = _node(
        "bendak_payload",
        flags=int(NodeFlags.HEADER | NodeFlags.MESH | NodeFlags.SKIN),
        parent=src_root,
    )
    mesh.vertices = [(-0.5, 0.0, 1.0), (0.5, 0.0, 0.1)]
    mesh.faces = [(0, 1, 1)]
    mesh.bone_map = ["L_Hand", "R_Foot"]
    mesh.skin_data = [
        VertexSkinData([BoneWeight(0, 1.0)]),
        VertexSkinData([BoneWeight(1, 1.0)]),
    ]
    mesh_model = KotorModel(name="bendak", root_node=src_root)

    kotor_root = _node("N_Mandalorian")
    _node("Lhand_g", parent=kotor_root)
    _node("rfoot_g", parent=kotor_root)
    template = KotorModel(name="n_mandalorian", root_node=kotor_root, supermodel="S_Female02")

    result = apply_template_rig(mesh_model, template, game="K1", scale_mode="manual")

    assert result["ok"] is True
    rigged_mesh = result["model"].find_node("bendak_payload")
    assert rigged_mesh is not None
    left_hand_index = rigged_mesh.bone_map.index("Lhand_g")
    right_foot_index = rigged_mesh.bone_map.index("rfoot_g")
    assert rigged_mesh.skin_data[0].influences[0].bone_index == left_hand_index
    assert math.isclose(rigged_mesh.skin_data[0].influences[0].weight, 1.0)
    assert rigged_mesh.skin_data[1].influences[0].bone_index == right_foot_index
    assert math.isclose(rigged_mesh.skin_data[1].influences[0].weight, 1.0)
    skin_binding = result["model"].metadata["character_builder_bind"]["skin_binding"]
    assert skin_binding["weighting_method"] == "imported_source_skin_remap"
    assert skin_binding["quality_stage"] == "source_skin_remap_first_pass"
    assert skin_binding["source_skin_remap"] is True
    assert skin_binding["donor_weight_transfer"] is False
    assert skin_binding["mesh_reports"][0]["source_skin_vertices"] == 2
    assert skin_binding["mesh_reports"][0]["fallback_vertices"] == 0


def test_apply_template_rig_refines_source_hand_weights_with_native_fingers() -> None:
    src_root = _node("import_root")
    mesh = _node(
        "bendak_hand_payload",
        flags=int(NodeFlags.HEADER | NodeFlags.MESH | NodeFlags.SKIN),
        parent=src_root,
    )
    mesh.vertices = [(-0.62, 0.1, 1.0)]
    mesh.faces = [(0, 0, 0)]
    mesh.bone_map = ["L_Hand"]
    mesh.skin_data = [VertexSkinData([BoneWeight(0, 1.0)])]
    mesh_model = KotorModel(name="bendak", root_node=src_root)

    kotor_root = _node("N_Mandalorian")
    hand = _node("Lhand_g", parent=kotor_root)
    hand.position = (-0.50, 0.0, 1.0)
    finger = _node("LaFngrB_g", parent=hand)
    finger.position = (-0.10, 0.1, 0.0)
    finger_tip = _node("LaFngrT_g", parent=finger)
    finger_tip.position = (-0.10, 0.1, 0.0)
    template = KotorModel(name="n_mandalorian", root_node=kotor_root, supermodel="S_Female02")

    result = apply_template_rig(mesh_model, template, game="K1", scale_mode="manual")

    assert result["ok"] is True
    rigged_mesh = result["model"].find_node("bendak_hand_payload")
    assert rigged_mesh is not None
    assert "Lhand_g" in rigged_mesh.bone_map
    assert "LaFngrB_g" in rigged_mesh.bone_map
    finger_index = rigged_mesh.bone_map.index("LaFngrB_g")
    assert any(inf.bone_index == finger_index for inf in rigged_mesh.skin_data[0].influences)
    skin_binding = result["model"].metadata["character_builder_bind"]["skin_binding"]
    assert skin_binding["source_skin_remap"] is True
    assert skin_binding["source_hand_refinement"] is True
    assert skin_binding["mesh_reports"][0]["source_hand_refinement_vertices"] == 1


def test_apply_template_rig_records_replaced_native_render_payload_nodes() -> None:
    src_root = _node("import_root")
    mesh = _node("bendak_payload", flags=int(NodeFlags.HEADER | NodeFlags.MESH), parent=src_root)
    mesh.vertices = [(0.0, 0.0, 0.0)]
    mesh.faces = [(0, 0, 0)]
    mesh_model = KotorModel(name="bendak", root_node=src_root)

    kotor_root = _node("N_Mandalorian")
    rootdummy = _node("rootdummy", parent=kotor_root)
    native_torso = _node(
        "Torso",
        flags=int(NodeFlags.HEADER | NodeFlags.MESH | NodeFlags.SKIN),
        parent=kotor_root,
    )
    native_torso.vertices = [(0.0, 0.0, 0.0), (0.0, 0.1, 0.0), (0.1, 0.0, 0.0)]
    native_torso.faces = [(0, 1, 2)]
    native_torso.texture = "N_Mandalorian01"
    native_helper = _node(
        "torso_g",
        flags=int(NodeFlags.HEADER | NodeFlags.MESH),
        parent=rootdummy,
    )
    native_helper.vertices = [(0.0, 0.0, 1.0)]
    native_helper.faces = [(0, 0, 0)]
    template = KotorModel(name="n_mandalorian", root_node=kotor_root, supermodel="S_Female02")

    result = apply_template_rig(mesh_model, template, game="K1", scale_mode="manual")

    assert result["ok"] is True
    rigged = result["model"]
    assert rigged.find_node("Torso") is None
    assert rigged.find_node("torso_g") is not None
    bind = rigged.metadata["character_builder_bind"]
    replaced = bind["native_base"]["replaced_render_payload_nodes"]
    assert replaced == [
        {
            "name": "Torso",
            "path": ["N_Mandalorian", "Torso"],
            "is_mesh": True,
            "is_skin": True,
            "vertex_count": 3,
            "face_count": 1,
            "texture": "N_Mandalorian01",
            "replacement": "imported_mesh_payload",
        }
    ]
    assert bind["native_base"]["replaced_render_payload_count"] == 1
    assert result["replaced_native_render_nodes"] == replaced


def test_apply_template_rig_preserves_kotor_helper_mesh_skeleton_hooks() -> None:
    src_root = _node("import_root")
    mesh = _node("body_mesh", flags=int(NodeFlags.HEADER | NodeFlags.MESH), parent=src_root)
    mesh.vertices = [(0.0, 0.0, 0.0)]
    mesh.faces = [(0, 0, 0)]
    mesh_model = KotorModel(name="body", root_node=src_root)

    kotor_root = _node("PMBAM")
    rootdummy = _node("rootdummy", parent=kotor_root)
    torso = _node("torsoUpr_g", flags=int(NodeFlags.HEADER | NodeFlags.MESH), parent=rootdummy)
    torso.vertices = [(0.0, 0.0, 1.0)]
    torso.faces = [(0, 0, 0)]
    headhook = _node("headhook", parent=torso)
    arm = _node("Rhand_g", flags=int(NodeFlags.HEADER | NodeFlags.MESH), parent=torso)
    arm.vertices = [(1.0, 0.0, 1.0)]
    arm.faces = [(0, 0, 0)]
    _node("rhand", parent=arm)
    render_skin = _node("Torso", flags=int(NodeFlags.HEADER | NodeFlags.MESH | NodeFlags.SKIN), parent=kotor_root)
    render_skin.vertices = [(0.0, 0.0, 0.0)]
    render_skin.faces = [(0, 0, 0)]
    template = KotorModel(name="pmbam", root_node=kotor_root)

    result = apply_template_rig(mesh_model, template, game="K1", scale_mode="manual")

    assert result["ok"] is True
    rigged = result["model"]
    assert rigged.find_node("headhook") is not None
    assert rigged.find_node("rhand") is not None
    assert rigged.find_node("torsoUpr_g") is not None
    assert rigged.find_node("Rhand_g") is not None
    assert rigged.find_node("Torso") is None
    assert rigged.find_node("torsoUpr_g").is_mesh is False
    assert rigged.find_node("Rhand_g").is_mesh is False
    native_snapshot = result["native_skeleton_snapshot"]
    assert native_snapshot is not None
    assert native_snapshot.node_count == 7
    assert native_snapshot.supermodel == "NULL"
    assert "headhook" in native_snapshot.hook_names
    assert native_snapshot.nodes[2].name == "torsoUpr_g"
    assert native_snapshot.nodes[2].is_mesh is True

    rigged_mesh = rigged.find_node("body_mesh")
    assert rigged_mesh is not None
    assert rigged_mesh.is_skin is True
    assert "torsoUpr_g" in rigged_mesh.bone_map
    assert "Rhand_g" in rigged_mesh.bone_map
    assert "rhand" in rigged_mesh.bone_map
    assert "headhook" not in rigged_mesh.bone_map
    assert len(rigged_mesh.skin_data) == 1
    total = sum(inf.weight for inf in rigged_mesh.skin_data[0].influences)
    assert math.isclose(total, 1.0)


def test_apply_template_rig_skin_data_satisfies_weight_validator() -> None:
    src_root = _node("import_root")
    mesh = _node("body_mesh", flags=int(NodeFlags.HEADER | NodeFlags.MESH), parent=src_root)
    mesh.vertices = [(0.0, 0.0, 0.0), (0.5, 0.0, 0.0)]
    mesh.faces = [(0, 1, 1)]
    mesh_model = KotorModel(name="body", root_node=src_root)

    kotor_root = _node("PMBAM")
    rootdummy = _node("rootdummy", parent=kotor_root)
    torso = _node("torso_g", flags=int(NodeFlags.HEADER | NodeFlags.MESH), parent=rootdummy)
    torso.position = (0.0, 0.0, 1.0)
    _node("headhook", parent=torso)
    _node("rhand", parent=torso)
    _node("lhand", parent=torso)
    template = KotorModel(name="pmbam", root_node=kotor_root)

    result = apply_template_rig(mesh_model, template, game="K1", scale_mode="manual")

    assert result["ok"] is True
    scene = CharacterScene(game_version="K1")
    scene.assign(PartSlot.HEADLESS_BODY, result["model"], resref="bendak")
    issues = ValidationService(scene).validate()
    assert "SKIN_MESH_UNRIGGED" not in {issue.code for issue in issues}
    assert "WEIGHT_ZERO_SUM" not in {issue.code for issue in issues}
    assert "WEIGHT_UNNORMALIZED" not in {issue.code for issue in issues}
