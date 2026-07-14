from __future__ import annotations


def _utc_bytes(tag: str, appearance_id: int) -> bytes:
    from pykotor.resource.formats.gff import GFF, GFFContent, bytes_gff

    gff = GFF(GFFContent.UTC)
    gff.root.set_string("Tag", tag)
    gff.root.set_uint16("Appearance_Type", appearance_id)
    return bytes_gff(gff)


def test_catalog_uses_real_tags_and_only_decorates_them_from_appearance_2da() -> None:
    from src.core.scripting.data_authoring import TwoDADocument
    from src.core.scripting.dialogue_participants import DialogueParticipantCatalogService

    appearance = TwoDADocument(
        ("label", "modela", "normalhead", "race"),
        ("0", "1"),
        (
            ("n_human", "p_hhm_a", "1", "human"),
            ("n_rodian", "n_rodian", "42", "rodian"),
        ),
    ).to_bytes()
    rows = DialogueParticipantCatalogService().build(
        placed_creatures=({"tag": "cantina_guard", "appearance_id": "1"},),
        utc_blueprints=(_utc_bytes("bartender_tag", 1),),
        dialogue_tags=("already_in_dialogue",),
        appearance_2da=appearance,
    )
    by_tag = {row.tag: row for row in rows}

    assert set(by_tag) == {
        "cantina_guard",
        "bartender_tag",
        "already_in_dialogue",
        "OWNER",
        "PLAYER",
    }
    assert "n_human" not in by_tag
    assert "n_rodian" not in by_tag
    assert by_tag["cantina_guard"].body_model == "n_rodian"
    assert by_tag["bartender_tag"].head == "42"
    assert by_tag["bartender_tag"].race == "rodian"
