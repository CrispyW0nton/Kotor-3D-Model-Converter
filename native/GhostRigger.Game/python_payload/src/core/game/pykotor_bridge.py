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


def list_animations_via_pykotor(mdl_bytes: bytes) -> list:
    """Return a list of animation names parsed from raw MDL bytes via PyKotor.

    Returns an empty list for invalid/empty input without raising.
    """
    if not mdl_bytes or len(mdl_bytes) < 12:
        return []
    try:
        model = load_model_from_bytes(mdl_bytes)
        if model is None:
            return []
        return [a.name for a in model.animations]
    except Exception:
        return []


def compare_model_animations(gr_model, mdl_bytes=None):
    """Compare animation lists between a KotorModel and raw MDL bytes.

    Returns a dict with keys:
      gr_anims      – list of animation names from the GhostRigger model
      pk_anims      – list from PyKotor parse (empty if mdl_bytes is None/invalid)
      only_in_gr    – names only in gr_model
      only_in_pk    – names only in pykotor parse
      in_both       – names in both
      pykotor_used  – bool, True if PyKotor parse succeeded
      discrepancy   – bool, True if the two lists differ
    """
    gr_anims = [a.name for a in getattr(gr_model, 'animations', [])]
    pk_anims: list = []
    pykotor_used = False

    if mdl_bytes:
        pk_anims = list_animations_via_pykotor(mdl_bytes)
        pykotor_used = len(pk_anims) > 0

    gr_set = set(gr_anims)
    pk_set = set(pk_anims)
    # discrepancy is only meaningful when PyKotor actually parsed the bytes.
    # When mdl_bytes is None or PyKotor parse failed, there is nothing to compare.
    discrepancy = pykotor_used and bool(gr_set.symmetric_difference(pk_set))
    return {
        'gr_anims':     gr_anims,
        'pk_anims':     pk_anims,
        'only_in_gr':   sorted(gr_set - pk_set),
        'only_in_pk':   sorted(pk_set - gr_set),
        'in_both':      sorted(gr_set & pk_set),
        'pykotor_used': pykotor_used,
        'discrepancy':  discrepancy,
    }


def validate_animations_via_pykotor(mdl_bytes: bytes) -> dict:
    """Validate animations in raw MDL bytes using PyKotor.

    Returns a dict with at minimum an 'ok' key (bool) and 'anims' list.
    Never raises.
    """
    if not mdl_bytes or len(mdl_bytes) < 12:
        return {'ok': False, 'anims': [], 'error': 'empty or too-short input'}
    try:
        anims = list_animations_via_pykotor(mdl_bytes)
        return {'ok': True, 'anims': anims, 'count': len(anims)}
    except Exception as exc:
        return {'ok': False, 'anims': [], 'error': str(exc)}
