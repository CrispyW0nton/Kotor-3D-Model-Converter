"""
pykotor_bridge.py — backward-compatibility shim.

All real logic is in kotor_loader.py (direct PyKotor calls).
This file re-exports every public and private name that existing code
or tests import from pykotor_bridge so nothing breaks.
"""

from .kotor_loader import (
    load_model_from_bytes,
    load_model_from_bytes   as load_model_from_bytes_via_pykotor,
    load_model_from_file    as load_model_via_pykotor,
    load_tpc_as_pil         as pykotor_tpc_to_pil,
    patch_tpc_header        as patch_tpc_for_pykotor,
    # internal helpers used by tests
    _convert_node           as _convert_single_node,
    _TYPE_FLAGS             as _NODETYPE_TO_FLAGS,
    _read_controllers       as _extract_base_controllers,
    # _fill_mesh_data kept with original 3-arg signature for test compat

    _read_skin_weights      as _fill_skin_data,
    _convert_anim           as _convert_animation,
    _mdl_to_kotormodel      as _convert_pkmdl_to_kotormodel,
    _fill_missing_normals   as _generate_missing_normals,
    _apply_bind_pose        as _apply_bind_pose_controllers,
)


def is_pykotor_available() -> bool:
    """PyKotor is always available (hard dependency in kotor_loader)."""
    return True


def _fill_mesh_data(_pk_node_unused, mesh_obj, gr) -> None:
    """Compat wrapper: old signature was (pk_node, mesh_obj, gr); pk_node ignored."""
    from .kotor_loader import _read_mesh
    _read_mesh(mesh_obj, gr)
