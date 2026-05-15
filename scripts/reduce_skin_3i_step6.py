"""Reduce the 3i Step 6 / Step 7 dumps for c_drexlf, c_brith, and
c_bomabeast to a small set of summary tables per audited creature.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable

DUMPS = (
    Path("diagnostics/skinning/2026_05/skin_c_drexlf_3i.jsonl"),
    Path("diagnostics/skinning/2026_05/skin_c_brith_3i.jsonl"),
    Path("diagnostics/skinning/2026_05/skin_c_bomabeast_3i.jsonl"),
)


def _records(path: Path) -> Iterable[dict]:
    if not path.exists():
        return []
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _reduce_one(path: Path) -> None:
    print()
    print(f"### {path.name}")
    records = list(_records(path))
    if not records:
        print(f"  (missing or empty: {path})")
        return
    print(f"  records: {len(records)}")

    print()
    print("  --- Step 6 top-level provenance summary ---")
    for r in records:
        s = r.get("pre_qbone_basis_provenance_summary", {}) or {}
        node = r.get("node", "?")
        print(
            f"    {node:>10s}  loader={s.get('loader_pretransform','?'):<48s}"
            f"  bind_t_norm={s.get('skin_bind_translation_norm')}"
            f"  bind_has_t={s.get('skin_bind_includes_translation_xoreos_does_not')}"
        )
        print(f"               classification={s.get('classification','?')}")

    print()
    print("  --- Step 7 top-level B-translation summary ---")
    for r in records:
        s = r.get("step7_b_translation_summary", {}) or {}
        node = r.get("node", "?")
        print(
            f"    {node:>10s}  f11_collapse_all={s.get('f11_collapses_to_production_in_all_probes')}"
            f"  f12_collapse_all={s.get('f12_collapses_to_production_in_all_probes')}"
            f"  f11_max_dx={s.get('f11_vs_production_max_max_abs')}"
            f"  f12_max_dx={s.get('f12_vs_production_max_max_abs')}"
        )
        print(f"               classification={s.get('classification','?')}")

    print()
    print("  --- per-probe Step 6 + Step 7 ---")
    header = (
        f"  {'node':>10s} {'role':>10s} {'vi':>4s} "
        f"{'raw=vbo':>8s} {'bind_dx':>8s} "
        f"{'rot_only_dx':>11s} "
        f"{'F11_vs_F1':>10s} {'F12_vs_F1':>10s} "
        f"{'F11=F1?':>8s} {'F12=F1?':>8s}"
    )
    print(header)
    for r in records:
        node = r.get("node", "?")
        for p in r.get("skin_transform_convention_probes", []) or []:
            prov = p.get("pre_qbone_basis_provenance", {}) or {}
            step7 = p.get("step7_b_translation", {}) or {}
            role = p.get("vertex_role", "")
            vi = p.get("vertex_index", -1)
            raw_vs_vbo = p.get("raw_vs_vbo_max_abs", -1)
            bind_dx = p.get("skin_bind_moves_raw_max_abs", -1)
            rot_only_dx = prov.get(
                "reference_pre_qbone_with_rotation_only_vs_production_vbo_max_abs",
                -1,
            )
            f11_dx = step7.get("f11_vs_production_max_abs", -1) or -1
            f12_dx = step7.get("f12_vs_production_max_abs", -1) or -1
            f11_eq = "yes" if step7.get("f11_collapses_to_production") else "no"
            f12_eq = "yes" if step7.get("f12_collapses_to_production") else "no"
            print(
                f"  {node:>10s} {role:>10s} {vi:>4d} "
                f"{raw_vs_vbo:>8.4f} {bind_dx:>8.4f} "
                f"{rot_only_dx:>11.6f} "
                f"{f11_dx:>10.6f} {f12_dx:>10.6f} "
                f"{f11_eq:>8s} {f12_eq:>8s}"
            )


def main() -> int:
    for p in DUMPS:
        _reduce_one(p)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
