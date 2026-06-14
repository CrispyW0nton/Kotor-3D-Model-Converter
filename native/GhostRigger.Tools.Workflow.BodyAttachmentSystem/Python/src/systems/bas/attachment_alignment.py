"""Default local alignment transforms for BAS attachment layers."""

from __future__ import annotations

from typing import Any


IDENTITY_BAS_LAYER_TRANSFORM: dict[str, list[float]] = {
    "position": [0.0, 0.0, 0.0],
    "rotation": [0.0, 0.0, 0.0, 1.0],
    "scale": [1.0, 1.0, 1.0],
}


_WEAPON_FAMILY_OFFSETS: tuple[tuple[tuple[str, ...], tuple[float, float, float]], ...] = (
    (("lghtsbr", "shortsbr", "dblsbr"), (0.0, 0.0, 0.0)),
    (("blstrrfl", "blstrcrbn", "bowcstr", "hvyrptbl", "rifle"), (0.0, 0.06, 0.09)),
    (("blstrpstl", "hldoblstr", "ionblstr", "stunbatn"), (0.0, 0.02, 0.035)),
    (("vbroshort", "shortswrd"), (0.0, 0.0, 0.035)),
    (("vbroswrd", "lngswrd"), (0.0, 0.0, 0.055)),
    (("dblswrd",), (0.0, 0.0, 0.06)),
)


def normalize_bas_resref(resref: str) -> str:
    """Return a lowercase model resref without MDL/MDX suffix noise."""
    text = str(resref or "").strip().lower()
    for suffix in (".mdl", ".mdx"):
        if text.endswith(suffix):
            text = text[: -len(suffix)]
    return text


def normalize_bas_transform(transform: dict[str, Any] | None = None) -> dict[str, list[float]]:
    """Coerce a partial BAS transform into the persisted transform shape."""
    transform = transform or {}

    def values(key: str, fallback: list[float]) -> list[float]:
        raw = transform.get(key, fallback)
        try:
            result = [float(value) for value in list(raw)[: len(fallback)]]
        except Exception:
            result = []
        while len(result) < len(fallback):
            result.append(float(fallback[len(result)]))
        return result

    return {
        "position": values("position", IDENTITY_BAS_LAYER_TRANSFORM["position"]),
        "rotation": values("rotation", IDENTITY_BAS_LAYER_TRANSFORM["rotation"]),
        "scale": values("scale", IDENTITY_BAS_LAYER_TRANSFORM["scale"]),
    }


def default_bas_attachment_transform(slot: str, resref: str) -> dict[str, list[float]]:
    """Return the default local layer transform for a BAS slot/model pair.

    These transforms are small socket-local grip offsets. They never change the
    live socket-following contract and they are safe to persist in BAS recipes.
    """
    slot_key = str(slot or "").strip().lower()
    res_key = normalize_bas_resref(resref)
    if slot_key not in {"left_weapon", "right_weapon"} or not res_key:
        return normalize_bas_transform()
    for tokens, position in _WEAPON_FAMILY_OFFSETS:
        if any(token in res_key for token in tokens):
            return normalize_bas_transform({"position": position})
    return normalize_bas_transform()
