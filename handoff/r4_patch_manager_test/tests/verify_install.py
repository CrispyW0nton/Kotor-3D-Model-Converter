"""Verify R4 installed override files against expected SHA-256 hashes."""

from __future__ import annotations

import argparse
import hashlib
from pathlib import Path
import sys


EXPECTED = {
    "override/pmbam.mdl": "bfcd3468838050d25159afa3c90d963fec1a06fcbfc64b6ea9982adc4a8be8df",
    "override/pmbam.mdx": "84dc9b42faa0b2004c0e10eef6ab0bc65e02ee7bffaca027b829574832a58154",
}


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify R4 Ghost Rigger override install")
    parser.add_argument("kotor_root", type=Path, help="KOTOR install root containing Override/override")
    args = parser.parse_args()

    failures: list[str] = []
    for rel_path, expected_hash in EXPECTED.items():
        candidate = args.kotor_root / rel_path
        if not candidate.exists():
            candidate = args.kotor_root / rel_path.replace("override/", "Override/")
        if not candidate.exists():
            failures.append(f"missing: {rel_path}")
            continue
        actual = sha256(candidate)
        if actual.lower() != expected_hash:
            failures.append(f"hash mismatch: {candidate} {actual} != {expected_hash}")
        else:
            print(f"ok: {candidate} {actual}")

    if failures:
        for failure in failures:
            print(f"ERROR: {failure}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
