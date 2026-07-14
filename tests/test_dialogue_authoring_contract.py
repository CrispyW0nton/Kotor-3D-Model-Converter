from __future__ import annotations

from contextlib import redirect_stdout
from io import StringIO

import pytest

from src.core.scripting.dialogue_contract import (
    DialogueAnimationSnapshot,
    DialogueIdentityRegistry,
    DialogueStuntSnapshot,
    apply_dialogue_link_fields,
    apply_dialogue_node_fields,
    apply_dialogue_settings,
    connect_existing_dialogue_node,
    delete_dialogue_node,
    remove_dialogue_link,
    retarget_dialogue_link,
    snapshot_dialogue_graph,
    snapshot_dialogue_link,
    snapshot_dialogue_node,
    snapshot_dialogue_settings,
    start_dialogue_at_existing_node,
    validate_dialogue_authoring,
    validate_dialogue_link,
    validate_dialogue_node,
)


def _dialogue_fixture():
    from pykotor.common.language import Gender, Language, LocalizedString
    from pykotor.common.misc import Color, ResRef
    from pykotor.resource.generics.dlg import DLG, DLGAnimation, DLGEntry, DLGLink, DLGReply, DLGStunt

    dialogue = DLG()
    dialogue.word_count = 14
    dialogue.on_abort = ResRef("ab_dialog")
    dialogue.on_end = ResRef("end_dialog")
    dialogue.skippable = True
    dialogue.ambient_track = ResRef("mus_area")
    dialogue.animated_cut = 1
    dialogue.camera_model = ResRef("cameramodel")
    dialogue.computer_type = dialogue.computer_type.__class__(1)
    dialogue.conversation_type = dialogue.conversation_type.__class__(2)
    dialogue.old_hit_check = True
    dialogue.unequip_hands = True
    dialogue.unequip_items = True
    dialogue.vo_id = "voice-set"
    dialogue.comment = "author note"
    dialogue.alien_race_owner = 4
    dialogue.post_proc_owner = 5
    dialogue.record_no_vo = 1
    dialogue.next_node_id = 42
    dialogue.delay_entry = 120
    dialogue.delay_reply = 220

    stunt = DLGStunt()
    stunt.participant = "OWNER"
    stunt.stunt_model = ResRef("stuntmodel")
    stunt.retained_extension = "stunt metadata"
    dialogue.stunts.append(stunt)

    entry = DLGEntry()
    entry.list_index = 0
    entry.speaker = "OWNER"
    entry.listener = "PLAYER"
    entry.text = LocalizedString(88, {0: "Embedded fallback", 1: "Female fallback"})
    entry.comment = "node note"
    entry.script1 = ResRef("on_entry")
    entry.script2 = ResRef("on_entry_b")
    for index in range(1, 6):
        setattr(entry, f"script1_param{index}", index)
        setattr(entry, f"script2_param{index}", index + 10)
    entry.script1_param6 = "alpha"
    entry.script2_param6 = "beta"
    entry.sound = ResRef("vo_sound")
    entry.sound_exists = 1
    entry.vo_resref = ResRef("vo_line")
    entry.wait_flags = 7
    entry.delay = -1
    entry.quest = "quest_tag"
    entry.quest_entry = 20
    entry.plot_index = 2
    entry.plot_xp_percentage = 0.75
    entry.camera_angle = 3
    entry.camera_anim = 9
    entry.camera_id = 12
    entry.camera_fov = 62.5
    entry.camera_height = 1.5
    entry.camera_effect = 2
    entry.target_height = 0.4
    entry.fade_type = 1
    entry.fade_color = Color(0.2, 0.3, 0.4, 1.0)
    entry.fade_delay = 0.1
    entry.fade_length = 0.8
    entry.alien_race_node = 6
    entry.emotion_id = 7
    entry.facial_id = 8
    entry.node_id = 40
    entry.post_proc_node = 9
    entry.unskippable = True
    entry.record_vo = True
    entry.record_no_vo_override = True
    entry.vo_text_changed = True
    entry.retained_extension = {"source": "unknown GFF field"}

    animation = DLGAnimation()
    animation.participant = "OWNER"
    animation.animation_id = 6
    animation.retained_extension = "animation metadata"
    entry.animations.append(animation)

    reply = DLGReply()
    reply.list_index = 0
    reply.text = LocalizedString.from_english("Tell me more.")

    starter = DLGLink(entry)
    starter.active1 = ResRef("start_ok")
    reply_link = DLGLink(reply)
    reply_link.active1 = ResRef("can_reply")
    reply_link.active2 = ResRef("has_item")
    reply_link.active1_not = True
    reply_link.active2_not = False
    reply_link.logic = True
    reply_link.display_inactive = True
    reply_link.comment = "OR branch"
    reply_link.is_child = True
    for index in range(1, 6):
        setattr(reply_link, f"active1_param{index}", index)
        setattr(reply_link, f"active2_param{index}", index + 10)
    reply_link.active1_param6 = "left"
    reply_link.active2_param6 = "right"
    reply_link.retained_extension = "link metadata"

    cycle_link = DLGLink(entry)
    cycle_link.comment = "return to shared entry"
    dialogue.starters.append(starter)
    entry.links.append(reply_link)
    reply.links.append(cycle_link)
    return dialogue, entry, reply, starter, reply_link, cycle_link, animation, stunt


def test_full_field_snapshots_cover_k1_and_k2_dlg_properties() -> None:
    dialogue, entry, _reply, _starter, reply_link, _cycle, _animation, _stunt = _dialogue_fixture()
    identities = DialogueIdentityRegistry()

    settings = snapshot_dialogue_settings(dialogue)
    assert settings.stunts == (DialogueStuntSnapshot("OWNER", "stuntmodel"),)
    assert settings.on_abort == "ab_dialog"
    assert settings.conversation_type == 2
    assert settings.next_node_id == 42

    node = snapshot_dialogue_node(entry, identities, tlk_lookup=lambda index: f"TLK line {index}")
    assert node.text == "TLK line 88"
    assert node.text_stringref == 88
    assert node.text_substrings == ((0, "Embedded fallback"), (1, "Female fallback"))
    assert node.script1_params == (1, 2, 3, 4, 5, "alpha")
    assert node.script2_params == (11, 12, 13, 14, 15, "beta")
    assert node.animations == (DialogueAnimationSnapshot("OWNER", 6),)
    assert node.camera_fov == 62.5
    assert node.fade_color == pytest.approx((0.2, 0.3, 0.4, 1.0))
    assert node.record_no_vo_override is True

    link = snapshot_dialogue_link(reply_link, identities)
    assert link.target_node_id
    assert link.active1_params == (1, 2, 3, 4, 5, "left")
    assert link.active2_params == (11, 12, 13, 14, 15, "right")
    assert link.logic is True
    assert link.display_inactive is True
    assert link.comment == "OR branch"


def test_partial_apply_preserves_unedited_objects_and_unknown_metadata() -> None:
    dialogue, entry, _reply, _starter, reply_link, _cycle, animation, stunt = _dialogue_fixture()
    original_localized = entry.text

    apply_dialogue_settings(dialogue, {"skippable": False, "stunts": [{"participant": "PLAYER", "stunt_model": "newstunt"}]})
    apply_dialogue_node_fields(
        entry,
        {
            "listener": "SECOND_LISTENER",
            "script1_params": (8, 7, 6, 5, 4, "changed"),
            "animations": [{"participant": "PLAYER", "animation_id": 15}],
        },
    )
    apply_dialogue_link_fields(reply_link, {"active1_not": False, "comment": "updated"})

    assert dialogue.stunts[0] is stunt
    assert stunt.retained_extension == "stunt metadata"
    assert str(stunt.stunt_model) == "newstunt"
    assert entry.text is original_localized
    assert entry.retained_extension == {"source": "unknown GFF field"}
    assert entry.animations[0] is animation
    assert animation.retained_extension == "animation metadata"
    assert entry.script1_param1 == 8
    assert entry.script1_param6 == "changed"
    assert reply_link.retained_extension == "link metadata"
    assert str(reply_link.active2) == "has_item"
    assert reply_link.display_inactive is True

    before = entry.listener
    with pytest.raises(ValueError, match="Unknown DLG authoring field"):
        apply_dialogue_node_fields(entry, {"not_a_real_field": 1})
    assert entry.listener == before


def test_localized_text_updates_preserve_other_languages_and_snapshot_reapply_preserves_tlk() -> None:
    _dialogue, entry, _reply, _starter, _reply_link, _cycle, _animation, _stunt = _dialogue_fixture()
    identities = DialogueIdentityRegistry()
    original_snapshot = snapshot_dialogue_node(entry, identities)

    apply_dialogue_node_fields(entry, original_snapshot)
    assert entry.text.stringref == 88
    assert dict(entry.text._substrings_internal) == {0: "Embedded fallback", 1: "Female fallback"}

    apply_dialogue_node_fields(entry, {"text": "Edited English line"})
    assert entry.text.stringref == -1
    assert entry.text.get(0, 0) == "Edited English line"
    assert entry.text.get(0, 1) == "Female fallback"

    apply_dialogue_node_fields(entry, {"text_stringref": 120, "text_substrings": {4: "German fallback"}})
    assert entry.text.stringref == 120
    assert dict(entry.text._substrings_internal) == {4: "German fallback"}


def test_graph_snapshot_keeps_stable_ids_for_cycles_and_shared_targets() -> None:
    dialogue, entry, reply, _starter, _reply_link, _cycle, _animation, _stunt = _dialogue_fixture()
    identities = DialogueIdentityRegistry()

    first = snapshot_dialogue_graph(dialogue, identities)
    second = snapshot_dialogue_graph(dialogue, identities)
    assert first == second
    assert len(first.nodes) == 2
    assert len(first.links) == 3
    entry_id = identities.node_id(entry)
    reply_id = identities.node_id(reply)
    assert {row.node_id for row in first.nodes} == {entry_id, reply_id}
    assert any(row.source_node_id == reply_id and row.target_node_id == entry_id for row in first.links)
    condition = next(row.condition for row in first.links if row.source_node_id == entry_id)
    assert condition == "NOT can_reply OR has_item"


def test_validation_reports_engine_format_hazards_and_k1_dropped_fields() -> None:
    dialogue, entry, _reply, _starter, reply_link, _cycle, _animation, _stunt = _dialogue_fixture()
    identities = DialogueIdentityRegistry()
    entry.script1 = "script_name_far_too_long"
    entry.camera_fov = 200.0
    entry.sound_exists = 0
    reply_link.active2 = reply_link.active2.__class__("")

    node_issues = validate_dialogue_node(entry, identities, game="K1")
    assert {row.code for row in node_issues} >= {
        "dialogue.resref_too_long",
        "dialogue.invalid_camera_fov",
        "dialogue.sound_exists_mismatch",
        "dialogue.k2_node_fields_ignored_for_k1",
    }
    link_issues = validate_dialogue_link(reply_link, identities, game="K1")
    assert {row.code for row in link_issues} >= {
        "dialogue.secondary_condition_missing",
        "dialogue.k2_link_fields_ignored_for_k1",
    }
    assert "dialogue.display_inactive_not_serialized" not in {
        row.code for row in link_issues
    }
    all_issues = validate_dialogue_authoring(dialogue, game="K1", identities=identities)
    assert any(row.blocking for row in all_issues)
    assert "dialogue.k2_settings_ignored_for_k1" in {row.code for row in all_issues}


def test_known_fields_roundtrip_through_pykotor_k2_writer() -> None:
    from pykotor.common.misc import Game
    from pykotor.resource.formats.gff import bytes_gff
    from pykotor.resource.generics.dlg import dismantle_dlg, read_dlg

    dialogue, _entry, _reply, _starter, _reply_link, _cycle, _animation, _stunt = _dialogue_fixture()
    with redirect_stdout(StringIO()):
        payload = bytes_gff(dismantle_dlg(dialogue, Game.K2))
        reloaded = read_dlg(payload)
    assert payload.startswith(b"DLG ")
    settings = snapshot_dialogue_settings(reloaded)
    assert settings.on_end == "end_dialog"
    assert settings.next_node_id == 42
    assert settings.stunts == (DialogueStuntSnapshot("OWNER", "stuntmodel"),)
    graph = snapshot_dialogue_graph(reloaded, DialogueIdentityRegistry())
    assert len(graph.nodes) == 2
    assert len(graph.links) == 3


def test_topology_links_existing_targets_and_cycles_without_replacing_objects() -> None:
    dialogue, entry, reply, _starter, _reply_link, cycle_link, _animation, _stunt = _dialogue_fixture()
    entry_metadata = entry.retained_extension
    cycle_metadata = cycle_link.comment

    shared = connect_existing_dialogue_node(dialogue, entry, reply)
    second_cycle = connect_existing_dialogue_node(dialogue, reply, entry)

    assert shared.node is reply
    assert second_cycle.node is entry
    assert shared.is_child is True
    assert second_cycle.is_child is True
    assert entry.retained_extension is entry_metadata
    assert cycle_link.comment == cycle_metadata
    issues = validate_dialogue_authoring(dialogue, game="K2")
    assert "dialogue.node_type_does_not_alternate" not in {row.code for row in issues}
    assert len(snapshot_dialogue_graph(dialogue).links) == 5


def test_topology_retarget_and_start_existing_preserve_link_identity_and_metadata() -> None:
    from pykotor.common.language import LocalizedString
    from pykotor.resource.generics.dlg import DLGEntry, DLGLink

    dialogue, entry, reply, _starter, _reply_link, cycle_link, _animation, _stunt = _dialogue_fixture()
    second_entry = DLGEntry()
    second_entry.speaker = "SECOND"
    second_entry.text = LocalizedString.from_english("A second entry")
    seed = DLGLink(second_entry)
    dialogue.starters.append(seed)
    cycle_link.retained_extension = {"keep": True}
    original_identity = id(cycle_link)

    returned = retarget_dialogue_link(dialogue, cycle_link, second_entry)
    extra_starter = start_dialogue_at_existing_node(dialogue, entry)

    assert returned is cycle_link
    assert id(returned) == original_identity
    assert returned.node is second_entry
    assert returned.retained_extension == {"keep": True}
    assert extra_starter.node is entry
    assert len(dialogue.starters) == 3
    assert reply.links[0] is cycle_link


def test_topology_refuses_non_alternating_and_invalid_starter_targets() -> None:
    dialogue, entry, reply, _starter, reply_link, _cycle, _animation, _stunt = _dialogue_fixture()

    with pytest.raises(ValueError, match="alternate"):
        connect_existing_dialogue_node(dialogue, entry, entry)
    with pytest.raises(ValueError, match="Starting links"):
        start_dialogue_at_existing_node(dialogue, reply)
    with pytest.raises(ValueError, match="alternate"):
        retarget_dialogue_link(dialogue, reply_link, entry)
    assert reply_link.node is reply


def test_delete_node_removes_all_incoming_links_and_keeps_survivors_stable() -> None:
    from pykotor.common.language import LocalizedString
    from pykotor.resource.generics.dlg import DLGEntry, DLGLink

    dialogue, entry, reply, starter, reply_link, cycle_link, _animation, _stunt = _dialogue_fixture()
    second_starter = start_dialogue_at_existing_node(dialogue, entry)
    survivor = DLGEntry()
    survivor.speaker = "SURVIVOR"
    survivor.text = LocalizedString.from_english("Still reachable")
    survivor_link = DLGLink(survivor)
    dialogue.starters.append(survivor_link)
    outgoing_container = entry.links

    removed = delete_dialogue_node(dialogue, entry)

    assert removed == 3
    assert all(link.node is not entry for link in dialogue.starters)
    assert all(link.node is not entry for link in reply.links)
    assert survivor_link in dialogue.starters
    assert survivor_link.node is survivor
    assert entry.links is outgoing_container
    assert entry.links == [reply_link]
    assert starter not in dialogue.starters
    assert second_starter not in dialogue.starters
    assert cycle_link not in reply.links


def test_remove_link_only_removes_selected_branch() -> None:
    dialogue, _entry, _reply, starter, _reply_link, _cycle, _animation, _stunt = _dialogue_fixture()
    other = start_dialogue_at_existing_node(dialogue, starter.node)

    assert remove_dialogue_link(dialogue, other) == 1
    assert dialogue.starters == [starter]
    assert remove_dialogue_link(dialogue, other) == 0
