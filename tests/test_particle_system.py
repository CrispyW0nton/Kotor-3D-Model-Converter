"""Focused tests for the KOTOR emitter particle core (src.core.particles)."""

from __future__ import annotations

import sys
import types
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.core.particles.emitter_data import (  # noqa: E402
    EmitterDefinition,
    EmitterFlags,
    controllers_to_channels,
    sample_channel,
)
from src.core.particles.emitter_library import (  # noqa: E402
    EmitterTemplate,
    load_library,
    mdl_bytes_may_contain_emitters,
    save_library,
    templates_from_model,
)
from src.core.particles.simulation import (  # noqa: E402
    EmitterSimulation,
    ModelParticleSystems,
    effective_params,
)


def _controller(ctrl_type: int, values, times=None):
    times = times if times is not None else [0.0]
    return {
        "type": ctrl_type,
        "name": f"ctrl_{ctrl_type}",
        "columns": len(values[0]),
        "times": list(times),
        "values": [list(row) for row in values],
    }


def _sun_gas_node():
    """Synthetic node mirroring K1 plc_starmap's Sun_gas emitter."""
    node = types.SimpleNamespace()
    node.name = "Sun_gas"
    node.is_emitter = True
    node.emitter_params = {
        "update": "Fountain",
        "emitter_render": "Normal",
        "blend": "Lighten",
        "texture": "plc_starmap_02",
        "xgrid": 1,
        "ygrid": 1,
        "twosidedtex": 1,
        "loop": 0,
        "flags": 0x142,
    }
    node.controllers = [
        _controller(88, [[50.0]]),            # birthrate
        _controller(120, [[2.0]]),            # lifeexp
        _controller(168, [[0.07]]),           # velocity
        _controller(160, [[360.0]]),          # spread (degrees form)
        _controller(84, [[1.0]]),             # alphastart
        _controller(216, [[1.0]]),            # alphamid
        _controller(80, [[0.0]]),             # alphaend
        _controller(144, [[0.15]]),           # sizestart
        _controller(232, [[0.15]]),           # sizemid
        _controller(148, [[0.05]]),           # sizeend
        _controller(224, [[0.5]]),            # percentmid
        _controller(392, [[1.0, 0.68, 0.0]]),  # colorstart
        _controller(284, [[1.0, 0.68, 0.0]]),  # colormid
        _controller(380, [[1.0, 0.68, 0.0]]),  # colorend
        _controller(8, [[0.0, 0.0, 0.0]]),    # position (must not become a channel)
    ]
    return node


def test_controller_table_decodes_retail_numbering():
    channels = controllers_to_channels(_sun_gas_node().controllers)
    assert channels["birthrate"][0][1][0] == 50.0
    assert channels["lifeexp"][0][1][0] == 2.0
    assert channels["alphastart"][0][1][0] == 1.0
    assert channels["alphaend"][0][1][0] == 0.0
    assert channels["sizeend"][0][1][0] == 0.05
    assert channels["colorstart"][0][1] == (1.0, 0.68, 0.0)
    assert "position" not in channels


def test_sample_channel_interpolates_and_clamps():
    rows = [(0.0, (0.0,)), (1.0, (10.0,))]
    assert sample_channel(rows, -1.0) == (0.0,)
    assert sample_channel(rows, 0.5) == (5.0,)
    assert sample_channel(rows, 9.0) == (10.0,)


def test_definition_node_round_trip():
    node = _sun_gas_node()
    defn = EmitterDefinition.from_node(node)
    assert defn.update == "Fountain"
    assert defn.blend == "Lighten"
    assert defn.texture == "plc_starmap_02"
    assert EmitterFlags.INHERIT in defn.flag_bits
    assert defn.value("birthrate") == 50.0

    defn.set_value("birthrate", 75.0)
    defn.apply_to_node(node)
    reread = EmitterDefinition.from_node(node)
    assert reread.value("birthrate") == 75.0
    # position controller preserved on the node
    assert any(int(c.get("type", -1)) == 8 for c in node.controllers)

    payload = defn.to_dict()
    from_dict = EmitterDefinition.from_dict(payload)
    assert from_dict.to_dict() == payload


def test_animation_channels_override_bind_pose():
    node = _sun_gas_node()
    defn = EmitterDefinition.from_node(node)
    base = effective_params(defn)
    assert base.birthrate == 50.0
    animated = effective_params(defn, {"birthrate": [(0.0, (5.0,))]}, anim_time=0.0)
    assert animated.birthrate == 5.0
    # channels the animation does not key keep the bind value
    assert animated.lifeexp == base.lifeexp == 2.0


def test_fountain_spawn_rate_and_lifetime():
    defn = EmitterDefinition.from_node(_sun_gas_node())
    sim = EmitterSimulation(defn, seed=7)
    params = effective_params(defn)
    identity = (0.0, 0.0, 0.0, 1.0)
    for _ in range(30):
        sim.update(1.0 / 30.0, params, identity)
    # birthrate 50/s over 1 second ≈ 50 alive (lifeexp 2 s, none expired yet)
    assert 45 <= sim.alive_count <= 55
    for _ in range(90):
        sim.update(1.0 / 30.0, params, identity)
    # steady state: birthrate * lifeexp = 100
    assert 85 <= sim.alive_count <= 115


def test_single_update_keeps_one_particle():
    node = _sun_gas_node()
    node.emitter_params["update"] = "Single"
    defn = EmitterDefinition.from_node(node)
    sim = EmitterSimulation(defn, seed=3)
    params = effective_params(defn)
    for _ in range(50):
        sim.update(0.05, params, (0.0, 0.0, 0.0, 1.0))
    assert sim.alive_count == 1


def test_batch_interpolates_size_alpha_color():
    defn = EmitterDefinition.from_node(_sun_gas_node())
    sim = EmitterSimulation(defn, seed=1)
    params = effective_params(defn)
    identity = (0.0, 0.0, 0.0, 1.0)
    for _ in range(60):
        sim.update(1.0 / 30.0, params, identity)
    batch = sim.build_batch(params, (1.0, 2.0, 3.0), identity, (0.0, -5.0, 0.0))
    assert batch is not None
    assert batch.texture == "plc_starmap_02"
    assert batch.blend == "Lighten"
    # near-death particles fade below 1/255 alpha and are culled from the batch
    assert sim.alive_count - 5 <= batch.count <= sim.alive_count
    assert batch.colors.shape == (batch.count, 4)
    # Sun_gas alpha fades from 1 toward 0 and size shrinks toward 0.05.
    assert batch.colors[:, 3].max() <= 1.0
    assert batch.sizes.min() >= 0.05 - 1e-5
    assert batch.sizes.max() <= 0.15 + 1e-5


def test_invisible_batches_are_culled():
    node = _sun_gas_node()
    node.controllers = [
        _controller(88, [[20.0]]),
        _controller(120, [[1.0]]),
        _controller(84, [[0.0]]),   # alphastart 0
        _controller(216, [[0.0]]),  # alphamid 0
        _controller(80, [[0.0]]),   # alphaend 0
    ]
    defn = EmitterDefinition.from_node(node)
    sim = EmitterSimulation(defn, seed=2)
    params = effective_params(defn)
    for _ in range(30):
        sim.update(1.0 / 30.0, params, (0.0, 0.0, 0.0, 1.0))
    assert sim.alive_count > 0
    assert sim.build_batch(params, (0, 0, 0), (0, 0, 0, 1), (0, -5, 0)) is None


def _model_with_emitter():
    node = _sun_gas_node()
    node.children = []
    node.parent = None
    node._gr_hidden = False
    model = types.SimpleNamespace()
    model.root_node = node
    model.all_nodes = lambda: [node]
    model.animations = []
    return model, node


def test_model_particle_systems_update_and_batches():
    model, node = _model_with_emitter()
    systems = ModelParticleSystems(model)
    assert systems.has_emitters

    def transform(_node):
        return (1.0, 0.0, 0.5), (0.0, 0.0, 0.0, 1.0)

    for _ in range(30):
        systems.update(1.0 / 30.0, transform)
    batches = systems.batches(transform, (0.0, -5.0, 1.0))
    assert len(batches) == 1
    assert batches[0].count > 10

    # Editing the node restarts its simulation
    systems.invalidate_node(node)
    assert systems.batches(transform, (0.0, -5.0, 1.0)) == []


def test_effect_records_graft_with_baked_transforms():
    from src.core.particles.emitter_library import build_effect_records, graft_particle_effects

    source_model, source_node = _model_with_emitter()
    # Parent the emitter under a 180°-about-X dummy: strict FK must lift the
    # baked position instead of collapsing the flip.
    dummy = types.SimpleNamespace()
    dummy.name = "Dummy01"
    dummy.position = (0.0, 0.0, -0.3)
    dummy.rotation = (1.0, 0.0, 0.0, 0.0)
    dummy.parent = None
    source_node.parent = dummy
    source_node.position = (0.0, 0.7, -2.0)
    source_node.rotation = (0.0, 0.0, 0.0, 1.0)

    records = build_effect_records(source_model, "K2", "plc_holopera")
    assert len(records) == 1
    record = records[0]
    x, y, z = record["base_position"]
    assert abs(x - 0.0) < 1e-6 and abs(y + 0.7) < 1e-6 and abs(z - 1.7) < 1e-6

    # Graft onto a fresh target model and verify the emitter arrives intact.
    from src.core.geometry.model_data import ModelNode, NodeFlags

    root = ModelNode(name="target_root", flags=int(NodeFlags.HEADER))
    target = types.SimpleNamespace()
    target.root_node = root

    def all_nodes():
        nodes = [root]
        stack = list(root.children)
        while stack:
            node = stack.pop()
            nodes.append(node)
            stack.extend(getattr(node, "children", []) or [])
        return nodes

    target.all_nodes = all_nodes
    record["offset"] = [0.0, 0.0, 0.5]
    grafted = graft_particle_effects(target, records)
    assert grafted == 1
    new_node = next(n for n in target.all_nodes() if getattr(n, "is_emitter", False))
    assert new_node.name.startswith("fx_plc_holopera_")
    assert abs(new_node.position[2] - 2.2) < 1e-6  # baked 1.7 + offset 0.5
    assert new_node.emitter_params.get("texture") == "plc_starmap_02"
    assert getattr(new_node, "_gr_grafted_particle_effect", False)


def test_library_prefilter_and_round_trip(tmp_path):
    assert mdl_bytes_may_contain_emitters(b"junk Fountain junk")
    assert not mdl_bytes_may_contain_emitters(b"no emitters here")

    model, _node = _model_with_emitter()
    templates = templates_from_model("K1", "plc_starmap", model)
    assert len(templates) == 1
    assert templates[0].key == "K1:plc_starmap:Sun_gas"

    path = tmp_path / "emitter_library_k1.json"
    save_library(path, "K1", templates)
    loaded = load_library(path)
    assert len(loaded) == 1
    assert loaded[0].definition == templates[0].definition
    assert isinstance(loaded[0], EmitterTemplate)
    assert loaded[0].emitter_definition().value("birthrate") == 50.0


def test_bloom_uses_luminance_gate_for_saturated_holograms():
    """Cyan emitter detail must not pass bloom as if it were white."""
    bloom_path = (
        ROOT
        / "native/GhostRigger.Core.Rendering/Python/src/adapters/rendering/moderngl_bloom.py"
    )
    source = bloom_path.read_text(encoding="utf-8")
    assert "dot(c, vec3(0.2126, 0.7152, 0.0722))" in source
    assert "smoothstep(u_threshold, 1.0, luminance)" in source
    assert "max(c - vec3(u_threshold)" not in source

    threshold = 0.82
    cyan_luminance = 0.7152 + 0.0722
    yellow_luminance = 0.2126 + 0.7152
    assert cyan_luminance < threshold < yellow_luminance


def test_bloom_quality_settings_round_trip_and_clamp():
    from src.core.rendering.renderer_settings import RendererSettings

    settings = RendererSettings.from_settings(
        {
            "renderer": {
                "bloom_enabled": False,
                "bloom_threshold": 1.25,
                "bloom_strength": 0.45,
            }
        }
    )
    assert settings.bloom_enabled is False
    assert settings.bloom_threshold == 1.25
    assert settings.bloom_strength == 0.45
    assert settings.to_settings_dict()["bloom_enabled"] is False

    clamped = RendererSettings.from_settings(
        {"renderer": {"bloom_threshold": 9.0, "bloom_strength": 4.0}}
    )
    assert clamped.bloom_threshold == 2.0
    assert clamped.bloom_strength == 1.0


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
