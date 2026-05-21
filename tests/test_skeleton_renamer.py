import json

import pytest

from src.core.retargeting.skeleton_renamer import (
    SkeletonRenameError,
    load_rename_spec,
    validate_rename_spec,
)


def test_load_valid_rename_spec():
    spec = load_rename_spec()
    assert spec.rename_pairs["lcollar_g"] == "clavicle_l"
    assert spec.explicit_non_scope
    assert len(spec.twist_leaves) == 8


def test_reject_spec_with_rest_pose_override():
    tmp_dir = __import__("pathlib").Path(".pytest_tmp_day45v6")
    tmp_dir.mkdir(exist_ok=True)
    path = tmp_dir / "bad_map.json"
    path.write_text(
        json.dumps(
            {
                "version": "x",
                "scope": "BONE_NAMING_ONLY",
                "rename_pairs": {},
                "rest_pose_override": {},
            }
        ),
        encoding="utf-8",
    )
    with pytest.raises(SkeletonRenameError):
        load_rename_spec(path)


def test_rename_collision_detected():
    spec = load_rename_spec()
    bad = type(spec)(
        version=spec.version,
        rename_pairs={"a": "pelvis", "b": "pelvis"},
        helper_bones_non_deform=[],
        twist_leaves=[],
        helper_leaves=[],
        unmapped_source_bones=[],
        explicit_non_scope=spec.explicit_non_scope,
    )
    errors = validate_rename_spec(bad, ["a", "b"])
    assert any("Rename collision" in err for err in errors)


def test_twist_leaf_parent_validation():
    spec = load_rename_spec()
    bad_leaf = type(spec.twist_leaves[0])(
        name="bad_twist",
        parent="missing_parent",
        local_translation_fraction=0.5,
        use_deform=False,
        vertex_weight_policy="zero",
    )
    bad = type(spec)(
        version=spec.version,
        rename_pairs={"rootdummy": "root"},
        helper_bones_non_deform=[],
        twist_leaves=[bad_leaf],
        helper_leaves=[],
        unmapped_source_bones=[],
        explicit_non_scope=spec.explicit_non_scope,
    )
    errors = validate_rename_spec(bad, ["rootdummy"])
    assert any("invalid parent" in err for err in errors)


def test_helper_bone_optional():
    spec = load_rename_spec()
    errors = validate_rename_spec(spec, list(spec.rename_pairs.keys()))
    assert not any("Helper bone" in err for err in errors)
