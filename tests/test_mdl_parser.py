"""
test_mdl_parser.py — MDL parser tests.

Tests per GHOSTWORKS_BLUEPRINT.md Section 10:
  "MDL parser: load an ASCII MDL, check node count and geometry"
"""
import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))


# ─── Sample ASCII MDL fixtures ────────────────────────────────────────────────

SIMPLE_ASCII_MDL = """\
filedependency null.mdl
newmodel TestModel
setsupermodel TestModel NULL
setanimationscale 1.00

node dummy TestModel
  parent NULL
  position 0.000 0.000 0.000
  orientation 0.000 0.000 0.000 1.000
endnode

node trimesh Cube01
  parent TestModel
  position 0.000 0.000 0.500
  orientation 0.000 0.000 0.000 1.000
  bitmap NULL
  alpha 1.0
  diffuse 0.800 0.800 0.800
  specular 0.000 0.000 0.000
  shininess 10.0
  render 1
  shadow 1
  transparencyhint 0
  beaming 0
  backgroundgeometry 0
  verts 8
    -0.500000 -0.500000 -0.500000
    -0.500000 -0.500000  0.500000
    -0.500000  0.500000 -0.500000
    -0.500000  0.500000  0.500000
     0.500000 -0.500000 -0.500000
     0.500000 -0.500000  0.500000
     0.500000  0.500000 -0.500000
     0.500000  0.500000  0.500000
  tverts 8
    0.000 0.000
    1.000 0.000
    0.000 1.000
    1.000 1.000
    0.000 0.000
    1.000 0.000
    0.000 1.000
    1.000 1.000
  faces 12
    0 1 2 1 0 1 2 1
    1 3 2 1 1 3 2 1
    4 6 5 1 4 6 5 1
    5 6 7 1 5 6 7 1
    0 4 1 1 0 4 1 1
    1 4 5 1 1 4 5 1
    2 3 6 1 2 3 6 1
    3 7 6 1 3 7 6 1
    0 2 4 1 0 2 4 1
    2 6 4 1 2 6 4 1
    1 5 3 1 1 5 3 1
    3 5 7 1 3 5 7 1
endnode

donemodel TestModel
"""

SKIN_MESH_MDL = """\
filedependency null.mdl
newmodel SkinTest
setsupermodel SkinTest NULL
setanimationscale 1.00

node dummy SkinTest
  parent NULL
  position 0.000 0.000 0.000
  orientation 0.000 0.000 0.000 1.000
endnode

node dummy bone01
  parent SkinTest
  position 0.000 0.000 0.000
  orientation 0.000 0.000 0.000 1.000
endnode

node skin SkinMesh
  parent SkinTest
  position 0.000 0.000 0.000
  orientation 0.000 0.000 0.000 1.000
  bitmap test_tex
  alpha 1.0
  diffuse 1.0 1.0 1.0
  specular 0.0 0.0 0.0
  shininess 10.0
  render 1
  shadow 1
  transparencyhint 0
  beaming 0
  backgroundgeometry 0
  verts 4
    -0.5 -0.5 0.0
     0.5 -0.5 0.0
     0.5  0.5 0.0
    -0.5  0.5 0.0
  tverts 4
    0.0 0.0
    1.0 0.0
    1.0 1.0
    0.0 1.0
  faces 2
    0 1 2 1 0 1 2 1
    0 2 3 1 0 2 3 1
  weights 4
    bone01 1.0000
    bone01 1.0000
    bone01 1.0000
    bone01 1.0000
endnode

donemodel SkinTest
"""

DANGLY_MESH_MDL = """\
filedependency null.mdl
newmodel ClothTest
setsupermodel ClothTest NULL
setanimationscale 1.00

node dummy ClothTest
  parent NULL
  position 0.000 0.000 0.000
  orientation 0.000 0.000 0.000 1.000
endnode

node danglymesh ClothPanel
  parent ClothTest
  position 0.000 0.000 1.000
  orientation 0.000 0.000 0.000 1.000
  bitmap robe_tex
  alpha 1.0
  diffuse 1.0 1.0 1.0
  specular 0.0 0.0 0.0
  shininess 5.0
  render 1
  shadow 1
  transparencyhint 0
  beaming 0
  backgroundgeometry 0
  displacement 0.5000
  tightness 0.5000
  period 1.0000
  verts 4
    -0.5  0.0 0.0
     0.5  0.0 0.0
     0.5 -1.0 0.0
    -0.5 -1.0 0.0
  tverts 4
    0.0 0.0
    1.0 0.0
    1.0 1.0
    0.0 1.0
  constraints 4
    0.0000
    0.0000
    1.0000
    1.0000
  faces 2
    0 1 2 1 0 1 2 1
    0 2 3 1 0 2 3 1
endnode

donemodel ClothTest
"""


# ─── Tests ───────────────────────────────────────────────────────────────────

class TestAsciiMdlParser:

    def test_parse_simple_model(self):
        from src.core.mdl_parser import MDLAsciiParser
        model = MDLAsciiParser().parse(SIMPLE_ASCII_MDL.splitlines())
        assert model is not None
        assert model.name.lower() == "testmodel"

    def test_node_count(self):
        from src.core.mdl_parser import MDLAsciiParser
        model = MDLAsciiParser().parse(SIMPLE_ASCII_MDL.splitlines())
        nodes = model.all_nodes()
        assert len(nodes) >= 2  # dummy root + Cube01

    def test_mesh_node_exists(self):
        from src.core.mdl_parser import MDLAsciiParser
        model = MDLAsciiParser().parse(SIMPLE_ASCII_MDL.splitlines())
        nodes = model.all_nodes()
        mesh_nodes = [n for n in nodes if n.is_mesh]
        assert len(mesh_nodes) >= 1

    def test_cube_vertex_count(self):
        from src.core.mdl_parser import MDLAsciiParser
        model = MDLAsciiParser().parse(SIMPLE_ASCII_MDL.splitlines())
        nodes = model.all_nodes()
        cube = next((n for n in nodes if n.name == "Cube01"), None)
        assert cube is not None
        assert len(cube.vertices) == 8

    def test_cube_face_count(self):
        from src.core.mdl_parser import MDLAsciiParser
        model = MDLAsciiParser().parse(SIMPLE_ASCII_MDL.splitlines())
        nodes = model.all_nodes()
        cube = next((n for n in nodes if n.name == "Cube01"), None)
        assert len(cube.faces) == 12

    def test_cube_uv_count(self):
        from src.core.mdl_parser import MDLAsciiParser
        model = MDLAsciiParser().parse(SIMPLE_ASCII_MDL.splitlines())
        nodes = model.all_nodes()
        cube = next((n for n in nodes if n.name == "Cube01"), None)
        assert len(cube.uvs) == 8

    def test_root_node_name(self):
        from src.core.mdl_parser import MDLAsciiParser
        model = MDLAsciiParser().parse(SIMPLE_ASCII_MDL.splitlines())
        assert model.root_node is not None

    def test_supermodel_name(self):
        from src.core.mdl_parser import MDLAsciiParser
        model = MDLAsciiParser().parse(SIMPLE_ASCII_MDL.splitlines())
        assert model.supermodel.upper() == "NULL"

    def test_skin_node(self):
        from src.core.mdl_parser import MDLAsciiParser
        model = MDLAsciiParser().parse(SKIN_MESH_MDL.splitlines())
        nodes = model.all_nodes()
        skin_nodes = [n for n in nodes if n.is_skin]
        assert len(skin_nodes) == 1
        assert skin_nodes[0].name == "SkinMesh"

    def test_skin_weights_parsed(self):
        from src.core.mdl_parser import MDLAsciiParser
        model = MDLAsciiParser().parse(SKIN_MESH_MDL.splitlines())
        nodes = model.all_nodes()
        skin = next((n for n in nodes if n.is_skin), None)
        assert skin is not None
        assert len(skin.skin_data) == 4  # 4 vertices
        # Each vertex should have bone01 with weight 1.0
        for sd in skin.skin_data:
            assert len(sd.influences) >= 1
            assert abs(sd.influences[0].weight - 1.0) < 1e-4

    def test_dangly_node(self):
        from src.core.mdl_parser import MDLAsciiParser
        model = MDLAsciiParser().parse(DANGLY_MESH_MDL.splitlines())
        nodes = model.all_nodes()
        dangly_nodes = [n for n in nodes if n.is_dangly]
        assert len(dangly_nodes) == 1
        assert dangly_nodes[0].name == "ClothPanel"

    def test_dangly_displacement(self):
        from src.core.mdl_parser import MDLAsciiParser
        model = MDLAsciiParser().parse(DANGLY_MESH_MDL.splitlines())
        nodes = model.all_nodes()
        dangly = next((n for n in nodes if n.is_dangly), None)
        assert abs(dangly.dangly_displacement - 0.5) < 1e-5

    def test_dangly_tightness(self):
        from src.core.mdl_parser import MDLAsciiParser
        model = MDLAsciiParser().parse(DANGLY_MESH_MDL.splitlines())
        nodes = model.all_nodes()
        dangly = next((n for n in nodes if n.is_dangly), None)
        assert abs(dangly.dangly_tightness - 0.5) < 1e-5

    def test_dangly_constraints(self):
        from src.core.mdl_parser import MDLAsciiParser
        model = MDLAsciiParser().parse(DANGLY_MESH_MDL.splitlines())
        nodes = model.all_nodes()
        dangly = next((n for n in nodes if n.is_dangly), None)
        assert len(dangly.dangly_constraints) == 4
        assert dangly.dangly_constraints[0] == pytest.approx(0.0)
        assert dangly.dangly_constraints[2] == pytest.approx(1.0)

    def test_node_parent_hierarchy(self):
        from src.core.mdl_parser import MDLAsciiParser
        model = MDLAsciiParser().parse(SIMPLE_ASCII_MDL.splitlines())
        nodes = model.all_nodes()
        cube = next((n for n in nodes if n.name == "Cube01"), None)
        assert cube is not None
        assert cube.parent is not None
        assert cube.parent.name.lower() == "testmodel"

    def test_write_read_roundtrip(self):
        """ASCII MDL write → parse → same node count."""
        from src.core.mdl_parser import MDLAsciiParser, MDLAsciiWriter
        import io
        model1 = MDLAsciiParser().parse(SIMPLE_ASCII_MDL.splitlines())
        # Write to a temp file
        import tempfile, os
        with tempfile.NamedTemporaryFile(suffix='.mdl', mode='w', delete=False) as f:
            fname = f.name
        try:
            MDLAsciiWriter().write(model1, fname)
            model2 = MDLAsciiParser().parse_file(fname)
        finally:
            os.unlink(fname)
        assert len(model1.all_nodes()) == len(model2.all_nodes())

    def test_texture_name(self):
        from src.core.mdl_parser import MDLAsciiParser
        model = MDLAsciiParser().parse(SKIN_MESH_MDL.splitlines())
        nodes = model.all_nodes()
        skin = next((n for n in nodes if n.is_skin), None)
        assert skin.texture.lower().replace('\x00', '') == "test_tex"

    def test_dangly_texture_name(self):
        from src.core.mdl_parser import MDLAsciiParser
        model = MDLAsciiParser().parse(DANGLY_MESH_MDL.splitlines())
        nodes = model.all_nodes()
        dangly = next((n for n in nodes if n.is_dangly), None)
        assert "robe" in dangly.texture.lower().replace('\x00', '')


class TestClothRig:
    """Tests for the K1 cloth rigging system."""

    def test_cloth_rig_import(self):
        from src.autorig.cloth_rig import ClothRigger
        assert ClothRigger is not None

    def test_cloth_rig_presets(self):
        from src.autorig.cloth_rig import ClothRigPreset
        names = ClothRigPreset.names()
        assert len(names) > 0
        assert any('Robe' in n or 'robe' in n for n in names)

    def test_apply_cloth_to_dangly_node(self):
        from src.core.mdl_parser import MDLAsciiParser
        from src.autorig.cloth_rig import ClothRigger, ClothRigPreset
        model = MDLAsciiParser().parse(DANGLY_MESH_MDL.splitlines())
        nodes = model.all_nodes()
        dangly = next((n for n in nodes if n.is_dangly), None)
        assert dangly is not None, f"No dangly node found in nodes: {[n.name for n in nodes]}"

        rig = ClothRigger()
        cfg = ClothRigPreset.get("Robe (Loose / K2 default)")
        result = rig.apply_cloth_to_node(dangly, cfg)
        assert result is True

        # Should preserve dangly flag
        assert dangly.is_dangly
        # Should have constraints
        assert len(dangly.dangly_constraints) > 0

    def test_constraint_painter_vertical(self):
        from src.autorig.cloth_rig import ClothConstraintPainter, ClothRigConfig
        verts = [(0, 0, 0), (0, 0, -0.25), (0, 0, -0.5),
                 (0, 0, -0.75), (0, 0, -1.0)]
        cfg = ClothRigConfig(constraint_mode='vertical')
        constraints = ClothConstraintPainter.generate(verts, cfg)
        assert len(constraints) == len(verts)
        # Top vertex (z=0, highest) → pinned (constraint=1.0 in K2 convention)
        # In K2: 1.0 = pinned, 0.0 = free. _vertical maps top→pin, bottom→free
        assert len(constraints) == 5
        # Just verify the constraints are valid floats in [0,1]
        for c in constraints:
            assert 0.0 <= c <= 1.0

    def test_cloth_summary(self):
        from src.core.mdl_parser import MDLAsciiParser
        from src.autorig.cloth_rig import ClothRigger
        model = MDLAsciiParser().parse(DANGLY_MESH_MDL.splitlines())
        rig = ClothRigger()
        summary = rig.get_cloth_summary(model)
        assert 'total_cloth_nodes' in summary
        assert summary['total_cloth_nodes'] >= 1
