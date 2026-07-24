"""Focused contracts for modular-head attachment and animation preview."""

from __future__ import annotations

from copy import deepcopy

from src.core.characters.head_attachment_preview import (
    build_head_attachment_preview,
)
from src.core.geometry.model_data import (
    Animation,
    KotorModel,
    ModelNode,
)


def _attach(parent: ModelNode, child: ModelNode) -> None:
    parent.children.append(child)
    child.parent = parent


def _body(*, supermodel: str = "S_Female03") -> KotorModel:
    root = ModelNode(name="PFBAM")
    torso = ModelNode(name="torso_g")
    hook = ModelNode(name="headhook", position=(0.0, 0.0, 1.5))
    _attach(root, torso)
    _attach(torso, hook)
    return KotorModel(
        name="PFBAM",
        supermodel=supermodel,
        root_node=root,
        animations=[],
    )


def _head(*, supermodel: str = "S_Female03") -> KotorModel:
    root = ModelNode(name="PFHA04")
    neck = ModelNode(name="neck_g")
    jaw = ModelNode(name="f_jaw_g")
    eye = ModelNode(name="eyeLA")
    _attach(root, neck)
    _attach(neck, jaw)
    _attach(neck, eye)
    return KotorModel(
        name="PFHA04",
        supermodel=supermodel,
        root_node=root,
        animations=[],
    )


def _supermodels() -> dict[str, KotorModel]:
    female03 = KotorModel(
        name="S_Female03",
        supermodel="S_Female02",
        root_node=ModelNode(name="S_Female03"),
        animations=[
            Animation(
                name="tlknorm",
                length=1.0,
                nodes=[
                    ModelNode(name="f_jaw_g"),
                    ModelNode(name="eyeLA"),
                    ModelNode(name="torso_g"),
                ],
            ),
            Animation(
                name="walk",
                length=2.0,
                nodes=[ModelNode(name="torso_g")],
            ),
        ],
    )
    female02 = KotorModel(
        name="S_Female02",
        supermodel="NULL",
        root_node=ModelNode(name="S_Female02"),
        animations=[
            Animation(
                name="talk",
                length=0.8,
                nodes=[ModelNode(name="f_jaw_g")],
            ),
            Animation(
                name="walk",
                length=9.0,
                nodes=[ModelNode(name="torso_g")],
            ),
        ],
    )
    return {
        "s_female03": female03,
        "s_female02": female02,
    }


def test_preview_attaches_copy_at_exact_hook_and_inherits_facial_clips() -> None:
    body = _body()
    head = _head()
    body_before = deepcopy(body)
    head_before = deepcopy(head)
    models = _supermodels()

    result = build_head_attachment_preview(
        body_model=body,
        head_model=head,
        game="K2",
        body_resref="PFBAM",
        head_resref="P_CUSTOMH",
        supermodel_loader=lambda resref: models.get(resref.casefold()),
        selected_animation_names=("tlknorm", "talk", "walk"),
    )

    assert result.report.accepted is True
    assert result.report.headhook_node_path == "PFBAM/torso_g/headhook"
    assert result.report.headhook_world_position == (0.0, 0.0, 1.5)
    assert result.report.preview_head_parent_name == "headhook"
    assert result.report.source_head_parent_name == ""
    assert result.head_model.root_node.parent.name == "headhook"
    assert result.preview_model is result.body_model
    assert body.root_node.parent is body_before.root_node.parent
    assert head.root_node.parent is head_before.root_node.parent
    assert head.animations == []
    assert result.head_model.animations == []
    assert result.report.source_head_local_animation_names == ()
    assert result.report.preview_head_local_animation_names == ()
    assert result.report.supermodel_chain == ("S_Female03", "S_Female02")
    assert result.report.selected_animation_names == (
        "tlknorm",
        "talk",
        "walk",
    )
    assert set(result.report.facial_animation_names) == {"talk", "tlknorm"}
    assert len(result.report.effective_animations) == 3
    assert (
        next(
            row
            for row in result.report.effective_animations
            if row.name == "walk"
        ).source_model
        == "S_Female03"
    )
    assert result.report.contract_sha256


def test_local_head_animation_overrides_inherited_animation() -> None:
    head = _head()
    head.animations = [
        Animation(
            name="tlknorm",
            length=3.0,
            nodes=[ModelNode(name="f_jaw_g")],
        )
    ]
    models = _supermodels()

    result = build_head_attachment_preview(
        body_model=_body(),
        head_model=head,
        game="K2",
        supermodel_loader=lambda resref: models.get(resref.casefold()),
        selected_animation_names=("tlknorm",),
    )

    row = next(
        item
        for item in result.report.effective_animations
        if item.name == "tlknorm"
    )
    assert result.report.accepted is True
    assert row.source_scope == "local"
    assert row.source_model == "PFHA04"
    assert row.length == 3.0
    assert result.head_model.animations[0].length == 3.0


def test_supermodel_mismatch_blocks_preview() -> None:
    models = _supermodels()

    result = build_head_attachment_preview(
        body_model=_body(supermodel="S_Male03"),
        head_model=_head(),
        game="K2",
        supermodel_loader=lambda resref: models.get(resref.casefold()),
    )

    assert result.report.accepted is False
    assert any(
        "supermodel mismatch" in issue.casefold()
        for issue in result.report.blocking_issues
    )


def test_missing_or_ambiguous_exact_headhook_blocks_preview() -> None:
    body = _body()
    body.root_node.children[0].children.clear()
    models = _supermodels()
    missing = build_head_attachment_preview(
        body_model=body,
        head_model=_head(),
        game="K2",
        supermodel_loader=lambda resref: models.get(resref.casefold()),
    )

    duplicate_body = _body()
    _attach(duplicate_body.root_node, ModelNode(name="HEADHOOK"))
    duplicate = build_head_attachment_preview(
        body_model=duplicate_body,
        head_model=_head(),
        game="K2",
        supermodel_loader=lambda resref: models.get(resref.casefold()),
    )

    assert missing.report.accepted is False
    assert duplicate.report.accepted is False
    assert any(
        "exactly one" in issue
        for issue in missing.report.blocking_issues
    )
    assert any(
        "exactly one" in issue
        for issue in duplicate.report.blocking_issues
    )


def test_unresolved_chain_and_no_facial_targets_block_preview() -> None:
    unresolved = build_head_attachment_preview(
        body_model=_body(),
        head_model=_head(),
        game="K2",
        supermodel_loader=lambda _resref: None,
    )
    no_face_model = KotorModel(
        name="S_Female03",
        supermodel="NULL",
        root_node=ModelNode(name="S_Female03"),
        animations=[
            Animation(
                name="walk",
                nodes=[ModelNode(name="torso_g")],
            )
        ],
    )
    no_face = build_head_attachment_preview(
        body_model=_body(),
        head_model=_head(),
        game="K2",
        supermodel_loader=lambda _resref: no_face_model,
        selected_animation_names=("walk",),
    )

    assert unresolved.report.accepted is False
    assert any(
        "could not be resolved" in issue
        for issue in unresolved.report.blocking_issues
    )
    assert no_face.report.accepted is False
    assert any(
        "facial nodes" in issue
        for issue in no_face.report.blocking_issues
    )
