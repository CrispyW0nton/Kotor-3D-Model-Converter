from __future__ import annotations

from contextlib import redirect_stdout
from dataclasses import FrozenInstanceError
from io import StringIO
from pathlib import Path

import pytest

from src.core.modules.map_studio_pie_dialogue import (
    PIE_DIALOGUE_BLOCKED,
    PIE_DIALOGUE_CHOOSING,
    PIE_DIALOGUE_ENDED,
    PIE_DIALOGUE_LISTENING,
    MapStudioPIEDialogueConditionTable,
    MapStudioPIEDialogueSession,
    load_map_studio_pie_dialogue_animation_policies,
    map_studio_pie_dialogue_line_interval,
)


def _bytes(dialogue) -> bytes:
    from pykotor.common.misc import Game
    from pykotor.resource.generics.dlg import bytes_dlg

    with redirect_stdout(StringIO()):
        return bytes_dlg(dialogue, Game.K2)


def _choice_dialogue():
    from pykotor.common.language import LocalizedString
    from pykotor.common.misc import ResRef
    from pykotor.resource.generics.dlg import DLG, DLGAnimation, DLGEntry, DLGLink, DLGReply

    dialogue = DLG()
    dialogue.skippable = True
    dialogue.on_end = ResRef("dlg_complete")

    greeting = DLGEntry()
    greeting.list_index = 0
    greeting.speaker = "OWNER"
    greeting.listener = "PLAYER"
    greeting.text = LocalizedString(4242)
    greeting.sound = ResRef("npc_greet")
    greeting.vo_resref = ResRef("npc_greet_vo")
    greeting.camera_angle = 3
    greeting.camera_id = 7
    greeting.camera_fov = 58.0
    greeting.camera_height = 1.5
    greeting.target_height = 0.4
    greeting.delay = 2500
    greeting.wait_flags = 3
    greeting.script1 = ResRef("on_greeting")
    animation = DLGAnimation()
    animation.participant = "OWNER"
    animation.animation_id = 10040
    greeting.animations.append(animation)

    ask = DLGReply()
    ask.list_index = 0
    ask.text = LocalizedString.from_english("Tell me what happened.")
    leave = DLGReply()
    leave.list_index = 1
    leave.text = LocalizedString.from_english("Goodbye.")
    answer = DLGEntry()
    answer.list_index = 1
    answer.speaker = "OWNER"
    answer.listener = "PLAYER"
    answer.text = LocalizedString.from_english("The exchange was attacked.")
    blank_end = DLGReply()
    blank_end.list_index = 2
    blank_end.text = LocalizedString.from_english("")

    ask_link = DLGLink(ask)
    ask_link.active1 = ResRef("knows_exchange")
    ask_link.active2 = ResRef("has_clearance")
    ask_link.logic = True
    greeting.links.extend((ask_link, DLGLink(leave)))
    ask.links.append(DLGLink(answer))
    answer.links.append(DLGLink(blank_end))
    dialogue.starters.append(DLGLink(greeting))
    return dialogue


def test_dialogue_session_resolves_tlk_and_walks_numbered_choices() -> None:
    session = MapStudioPIEDialogueSession(
        _bytes(_choice_dialogue()),
        game="K2",
        resref="bardroid",
        owner_id="creature:drdbar",
        listener_id="player",
        tlk_lookup=lambda stringref: {4242: "You look like you need information."}.get(stringref, ""),
    )

    listening = session.start()

    assert listening.state == PIE_DIALOGUE_LISTENING
    assert listening.text == "You look like you need information."
    assert listening.speaker_tag == "OWNER"
    assert listening.listener_tag == "PLAYER"
    assert listening.sound_resref == "npc_greet"
    assert listening.voice_resref == "npc_greet_vo"
    assert listening.camera_angle == 3
    # Retail discards CameraID unless CameraAngle is the placed-camera mode 6.
    assert listening.camera_id is None
    assert listening.camera_fov == pytest.approx(58.0)
    assert listening.camera_height_offset == pytest.approx(1.5)
    assert listening.target_height_offset == pytest.approx(0.4)
    assert listening.delay == 2500
    assert listening.wait_flags == 3
    assert listening.line_interval_seconds >= 2.5
    assert listening.animations == (("OWNER", 10040),)
    assert listening.can_continue is True
    assert {event.kind for event in listening.events} >= {
        "conversation_started",
        "node_scripts_deferred",
        "entry_presented",
    }

    choosing = session.continue_dialogue()

    assert choosing.state == PIE_DIALOGUE_CHOOSING
    assert [choice.number for choice in choosing.choices] == [1, 2]
    assert [choice.text for choice in choosing.choices] == ["Tell me what happened.", "Goodbye."]
    assert choosing.choices[0].condition_resrefs == ("knows_exchange", "has_clearance")
    assert choosing.choices[0].condition_logic == "OR"
    assert choosing.choices[0].preview_assumed is True
    assert any(event.kind == "condition_preview_assumed" for event in choosing.events)

    rejected = session.choose(9)
    assert rejected.state == PIE_DIALOGUE_CHOOSING
    assert any(event.kind == "choice_rejected" for event in rejected.events)

    answer = session.choose(1)
    assert answer.state == PIE_DIALOGUE_LISTENING
    assert answer.text == "The exchange was attacked."

    ended = session.continue_dialogue()
    assert ended.state == PIE_DIALOGUE_ENDED
    assert ended.ended is True
    assert ended.choices == ()
    assert {event.kind for event in ended.events} >= {
        "blank_reply_glue",
        "conversation_end_script_deferred",
        "conversation_ended",
    }

    with pytest.raises(FrozenInstanceError):
        listening.text = "mutated"
    with pytest.raises(FrozenInstanceError):
        choosing.choices[0].text = "mutated"
    with pytest.raises(FrozenInstanceError):
        choosing.events[0].kind = "mutated"


def test_dialogue_camera_normalization_and_line_interval_contract() -> None:
    dialogue = _choice_dialogue()
    greeting = dialogue.starters[0].node
    greeting.camera_angle = 6
    greeting.camera_id = 7
    greeting.camera_fov = 0.0
    placed = MapStudioPIEDialogueSession(_bytes(dialogue)).start()
    assert placed.camera_id == 7
    assert placed.camera_fov is None

    assert map_studio_pie_dialogue_line_interval(
        "short",
        delay_seconds=4,
        audio_duration_seconds=1.25,
    ) == pytest.approx(4.0)
    assert map_studio_pie_dialogue_line_interval(
        "This text fallback is deliberately longer.",
        audio_duration_seconds=8.5,
    ) == pytest.approx(8.5)
    assert map_studio_pie_dialogue_line_interval("", audio_duration_seconds=None) == pytest.approx(1.0)


def test_dialoganimations_policy_preserves_fireforget_looping_and_overlay_flags() -> None:
    from pykotor.resource.formats.twoda import TwoDA, bytes_2da

    table = TwoDA(["name", "dialog", "fireforget", "looping", "overlay"])
    table.add_row(
        "10040",
        {
            "name": "TalkLoop",
            "dialog": "1",
            "fireforget": "0",
            "looping": "1",
            "overlay": "1",
        },
    )
    table.add_row(
        "10041",
        {
            "name": "GestureOnce",
            "dialog": "1",
            "fireforget": "1",
            "looping": "0",
            "overlay": "0",
        },
    )
    policies = load_map_studio_pie_dialogue_animation_policies(bytes_2da(table))
    assert policies[10040].looping and policies[10040].overlay
    assert not policies[10040].fire_and_forget
    assert policies[10041].fire_and_forget and not policies[10041].looping


def test_blank_entry_and_reply_glue_are_followed_without_fake_choices() -> None:
    from pykotor.common.language import LocalizedString
    from pykotor.resource.generics.dlg import DLG, DLGEntry, DLGLink, DLGReply

    dialogue = DLG()
    blank_entry = DLGEntry()
    blank_entry.list_index = 0
    blank_entry.text = LocalizedString.from_english("")
    blank_reply = DLGReply()
    blank_reply.list_index = 0
    blank_reply.text = LocalizedString.from_english("")
    visible_entry = DLGEntry()
    visible_entry.list_index = 1
    visible_entry.text = LocalizedString.from_english("Visible after glue.")
    blank_entry.links.append(DLGLink(blank_reply))
    blank_reply.links.append(DLGLink(visible_entry))
    dialogue.starters.append(DLGLink(blank_entry))

    snapshot = MapStudioPIEDialogueSession(_bytes(dialogue)).start()

    assert snapshot.state == PIE_DIALOGUE_LISTENING
    assert snapshot.text == "Visible after glue."
    assert snapshot.choices == ()
    assert {event.kind for event in snapshot.events} >= {
        "blank_entry_glue",
        "blank_reply_glue",
        "entry_presented",
    }


def test_blank_glue_cycle_is_blocked_instead_of_recursing_forever() -> None:
    from pykotor.common.language import LocalizedString
    from pykotor.resource.generics.dlg import DLG, DLGEntry, DLGLink, DLGReply

    dialogue = DLG()
    blank_entry = DLGEntry()
    blank_entry.list_index = 0
    blank_entry.text = LocalizedString.from_english("")
    blank_reply = DLGReply()
    blank_reply.list_index = 0
    blank_reply.text = LocalizedString.from_english("")
    blank_entry.links.append(DLGLink(blank_reply))
    blank_reply.links.append(DLGLink(blank_entry))
    dialogue.starters.append(DLGLink(blank_entry))

    snapshot = MapStudioPIEDialogueSession(_bytes(dialogue), max_auto_hops=8).start()

    assert snapshot.state == PIE_DIALOGUE_BLOCKED
    assert snapshot.blocked is True
    assert snapshot.ended is True
    assert snapshot.warnings
    assert any(event.kind == "automatic_cycle_blocked" for event in snapshot.events)


def test_abort_ends_active_preview_without_executing_abort_script() -> None:
    from pykotor.common.misc import ResRef

    dialogue = _choice_dialogue()
    dialogue.on_abort = ResRef("dlg_abort")
    session = MapStudioPIEDialogueSession(_bytes(dialogue))
    session.start()

    snapshot = session.abort()

    assert snapshot.state == PIE_DIALOGUE_ENDED
    assert {event.kind for event in snapshot.events} >= {
        "conversation_end_script_deferred",
        "conversation_aborted",
    }
    assert any("dlg_abort" in event.resrefs for event in snapshot.events)


def test_unknown_starter_cannot_hide_later_known_true_fallback() -> None:
    from pykotor.common.language import LocalizedString
    from pykotor.common.misc import ResRef
    from pykotor.resource.generics.dlg import DLG, DLGEntry, DLGLink

    dialogue = DLG()
    uncertain = DLGEntry()
    uncertain.list_index = 0
    uncertain.text = LocalizedString.from_english("Unknown branch")
    uncertain_link = DLGLink(uncertain)
    uncertain_link.active1 = ResRef("unknown_gate")
    fallback = DLGEntry()
    fallback.list_index = 1
    fallback.text = LocalizedString.from_english("Known fallback")
    dialogue.starters.extend((uncertain_link, DLGLink(fallback)))

    snapshot = MapStudioPIEDialogueSession(_bytes(dialogue)).start()

    assert snapshot.text == "Known fallback"
    assert any(event.kind == "condition_unknown" for event in snapshot.events)
    assert not any(event.kind == "condition_preview_assumed" for event in snapshot.events)

    only_unknown = DLG()
    only_unknown.starters.append(uncertain_link)
    assumed = MapStudioPIEDialogueSession(_bytes(only_unknown)).start()
    assert assumed.text == "Unknown branch"
    assert any(event.kind == "condition_preview_assumed" for event in assumed.events)


def test_active2_not_and_three_valued_logic_filter_player_replies() -> None:
    from pykotor.common.language import LocalizedString
    from pykotor.common.misc import ResRef
    from pykotor.resource.generics.dlg import DLG, DLGEntry, DLGLink, DLGReply

    dialogue = DLG()
    greeting = DLGEntry()
    greeting.list_index = 0
    greeting.text = LocalizedString.from_english("Choose.")

    def reply(text: str, first: str, second: str = "", *, logic: bool = False, negate_first: bool = False):
        node = DLGReply()
        node.text = LocalizedString.from_english(text)
        link = DLGLink(node)
        link.active1 = ResRef(first)
        link.active2 = ResRef(second)
        link.logic = logic
        link.active1_not = negate_first
        return link

    greeting.links.extend(
        (
            reply("AND false", "yes", "no"),
            reply("OR true", "yes", "no", logic=True),
            reply("NOT true", "no", negate_first=True),
            reply("Unknown AND false", "missing", "no"),
            reply("Unknown OR true", "missing", "yes", logic=True),
            reply("Unknown preview", "missing"),
        )
    )
    dialogue.starters.append(DLGLink(greeting))
    table = MapStudioPIEDialogueConditionTable({"yes": True, "no": False})
    session = MapStudioPIEDialogueSession(_bytes(dialogue), condition_evaluator=table)
    session.start()

    choosing = session.continue_dialogue()

    assert [choice.text for choice in choosing.choices] == [
        "OR true",
        "NOT true",
        "Unknown OR true",
        "Unknown preview",
    ]
    assert [choice.condition_state for choice in choosing.choices] == [
        "true",
        "true",
        "true",
        "unknown",
    ]
    assert choosing.choices[-1].preview_assumed is True
    assert any(event.kind == "condition_evaluated_false" for event in choosing.events)
    assert any(event.kind == "condition_preview_assumed" for event in choosing.events)


_K2_ROOT = Path(r"C:\Program Files (x86)\Steam\steamapps\common\Knights of the Old Republic II")


@pytest.mark.skipif(
    not (_K2_ROOT / "Modules" / "207TEL.mod").is_file() or not (_K2_ROOT / "dialog.tlk").is_file(),
    reason="The exact local 207TEL dialogue fixture is not installed.",
)
def test_real_207falt_normal_pc_state_selects_so_youre_back_with_four_replies() -> None:
    """The exact user fixture no longer assumes its B-4D4 starter true.

    PyKotor inspection shows six ordered starters: c_b4d4pc, c_talkedto,
    three parameterized c_chk202falt branches, then the unconditional normal
    PC branch.  Values here are bounded fixture state, not arbitrary NCS
    execution; exact c_global_eq calls are keyed by their six DLG parameters.
    """

    from pykotor.extract.capsule import LazyCapsule
    from pykotor.resource.formats.tlk import read_tlk
    from pykotor.resource.type import ResourceType

    capsule = LazyCapsule(str(_K2_ROOT / "Modules" / "207TEL.mod"))
    payload = capsule.resource("207falt", ResourceType.DLG)
    assert payload
    talk_table = read_tlk(_K2_ROOT / "dialog.tlk")
    conditions = MapStudioPIEDialogueConditionTable(
        {
            "c_b4d4pc": False,
            "c_talkedto": False,
            "c_chk202falt": False,
            "c_ismale": True,
            "c_isfemale": False,
        },
        by_request={
            ("c_global_eq", (5, 0, 0, 0, 0, "203TEL_DroidInt_1")): True,
            ("c_global_eq", (3, 0, 0, 0, 0, "200TEL_Falt_Arrest")): True,
        },
    )
    session = MapStudioPIEDialogueSession(
        payload,
        game="K2",
        resref="207falt",
        owner_id="creature:207falt",
        listener_id="pie:player",
        tlk_lookup=lambda stringref: talk_table.entries[stringref].text,
        condition_evaluator=conditions,
    )

    greeting = session.start()
    choosing = session.continue_dialogue()

    assert greeting.text == "So you're back."
    assert len(choosing.choices) == 4
    assert [choice.text for choice in choosing.choices] == [
        "What can you tell me about Czerka?",
        "What do you do at Czerka?",
        "I want to talk to you about Lorso.",
        "I'll be going now.",
    ]
    assert all(choice.condition_state == "true" for choice in choosing.choices)
