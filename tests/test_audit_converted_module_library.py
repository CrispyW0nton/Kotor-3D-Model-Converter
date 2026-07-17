from __future__ import annotations

from scripts.audit_converted_module_library import compare_artifact_drift


def _report(mod_hash: str, kmap_hash: str = "kmap") -> dict[str, object]:
    return {
        "targets": [
            {
                "module": "example",
                "game": "K2",
                "mod": {"path": "example.mod", "size": 10, "sha256": mod_hash},
                "kmap": {"path": "example.kmap", "size": 20, "sha256": kmap_hash},
            }
        ]
    }


def test_artifact_drift_is_empty_for_identical_hash_bound_targets() -> None:
    assert compare_artifact_drift(_report("same"), _report("same")) == []


def test_artifact_drift_records_prior_and_current_hashes() -> None:
    drift = compare_artifact_drift(_report("before"), _report("after"))

    assert len(drift) == 1
    assert drift[0]["artifact"] == "mod"
    assert drift[0]["before"]["sha256"] == "before"
    assert drift[0]["after"]["sha256"] == "after"


def test_artifact_drift_records_removed_target() -> None:
    drift = compare_artifact_drift(_report("before"), {"targets": []})

    assert drift == [
        {
            "module": "example",
            "game": "K2",
            "artifact": "target",
            "change": "removed",
        }
    ]
