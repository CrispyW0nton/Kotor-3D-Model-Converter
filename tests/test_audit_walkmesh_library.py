from __future__ import annotations


from scripts.audit_walkmesh_library import compare_mod_kmap_walkmeshes


def _walkmesh(resref: str, semantic: str, *, faces: int = 2, vertices: int | None = None) -> dict:
    return {
        "resref": resref,
        "raw_structure_valid": True,
        "fingerprints": {
            "semantic": semantic,
            "adjacency": f"adj-{semantic}",
            "transition_records": f"trans-{semantic}",
        },
        "counts": {
            "vertices": (faces + 2 if faces else 0) if vertices is None else vertices,
            "faces": faces,
            "walkable_material_faces": faces,
            "nonwalk_material_faces": 0,
            "adjacency_domain_faces": faces,
        },
        "surface_distribution": {1: faces} if faces else {},
        "perimeters": {
            "boundary_edge_id_hash": f"edges-{semantic}",
            "perimeter_loop_count": 1 if faces else 0,
        },
    }


def test_mod_kmap_walkmesh_parity_accepts_matching_room_semantics() -> None:
    mod = {"audit_pass": True, "walkmeshes": [_walkmesh("room01", "same")]}
    kmap = {"audit_pass": True, "walkmeshes": [_walkmesh("ROOM01", "same")]}

    parity = compare_mod_kmap_walkmeshes(mod, kmap)

    assert parity["all_match"] is True
    assert parity["mismatch_rooms"] == []
    assert parity["missing_in_kmap"] == []
    assert parity["extra_in_kmap"] == []


def test_mod_kmap_walkmesh_parity_rejects_empty_wok_becoming_generated_faces() -> None:
    mod = {"audit_pass": True, "walkmeshes": [_walkmesh("visual01", "empty", faces=0)]}
    kmap = {"audit_pass": True, "walkmeshes": [_walkmesh("visual01", "fallback", faces=2)]}

    parity = compare_mod_kmap_walkmeshes(mod, kmap)

    assert parity["all_match"] is False
    assert parity["mismatch_rooms"] == ["visual01"]
    comparison = parity["room_comparisons"][0]
    assert comparison["semantic_match"] is False
    assert comparison["count_mismatches"]["faces"] == {"mod": 0, "kmap": 2}


def test_mod_kmap_walkmesh_parity_treats_unreferenced_vertex_drift_as_diagnostic() -> None:
    # A source WOK carrying one unreferenced legacy vertex (774qgm_01a,
    # cor_m56ag) must not fail parity when semantic geometry, materials,
    # adjacency, perimeters, and transitions match exactly.
    mod = {"audit_pass": True, "walkmeshes": [_walkmesh("room01", "same", faces=4, vertices=7)]}
    kmap = {"audit_pass": True, "walkmeshes": [_walkmesh("room01", "same", faces=4, vertices=6)]}

    parity = compare_mod_kmap_walkmeshes(mod, kmap)

    assert parity["all_match"] is True
    assert parity["mismatch_rooms"] == []
    comparison = parity["room_comparisons"][0]
    assert comparison["match"] is True
    assert comparison["count_mismatches"] == {}
    assert comparison["diagnostic_count_mismatches"]["vertices"] == {"mod": 7, "kmap": 6}


def test_mod_kmap_walkmesh_parity_still_blocks_face_count_drift() -> None:
    mod = {"audit_pass": True, "walkmeshes": [_walkmesh("room01", "same", faces=4)]}
    kmap = {"audit_pass": True, "walkmeshes": [_walkmesh("room01", "same", faces=5, vertices=6)]}

    parity = compare_mod_kmap_walkmeshes(mod, kmap)

    assert parity["all_match"] is False
    assert parity["mismatch_rooms"] == ["room01"]
    comparison = parity["room_comparisons"][0]
    assert comparison["count_mismatches"]["faces"] == {"mod": 4, "kmap": 5}
