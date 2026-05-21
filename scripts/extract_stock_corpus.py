#!/usr/bin/env python
"""Extract GhostRigger's isolated stock KOTOR retargeting corpus.

This one-shot extractor reads MDL/MDX resources directly from ``chitin.key`` /
BIF-backed stock data and writes them to ``tests/fixtures/kotor_stock``. It
does not call the ResourceManager priority lookup and therefore never reads
``Override/``. Re-run it when you need to regenerate the local corpus.

Usage:
    python scripts/extract_stock_corpus.py ^
        --kotor-install "C:/Program Files (x86)/Steam/steamapps/common/swkotor" ^
        --game k1 ^
        --output tests/fixtures/kotor_stock/
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from src.core.resource_manager import RES_MDL, RES_MDX, _GameInstall, _key


SUPERMODEL_RESREFS = [
    "S_Male01",
    "S_Male02",
    "S_Female01",
    "S_Female02",
    "S_Female03",
]

PC_BODY_RESREFS = [
    "pmbam",
    "pfbam",
]


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _read_bif_resource(install: _GameInstall, resref: str, res_type: int) -> tuple[bytes, str]:
    """Read a resource from BIF/chitin only, bypassing Override and modules."""

    slot = install._key_map.get(_key(resref, res_type))
    if slot is None:
        raise FileNotFoundError(f"{resref}:{res_type} not found in chitin.key/BIF")
    bif_idx, var_idx = slot
    bif = install._bif_index.get(bif_idx)
    if bif is None:
        raise FileNotFoundError(f"BIF index {bif_idx} for {resref}:{res_type} is unavailable")
    data = bif.read(var_idx)
    if data is None:
        raise IOError(f"failed to read {resref}:{res_type} from {bif.path}")
    return data, str(Path(bif.path))


def _write_resource(
    install: _GameInstall,
    out_dir: Path,
    rel_dir: str,
    resref: str,
    ext: str,
    res_type: int,
) -> dict[str, Any]:
    data, source_path = _read_bif_resource(install, resref, res_type)
    rel_path = Path(rel_dir) / f"{resref}.{ext}"
    out_path = out_dir / rel_path
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_bytes(data)
    return {
        "path": str(rel_path).replace("\\", "/"),
        "sha256": _sha256(data),
        "size_bytes": len(data),
        "source_resref": resref,
        "source_type": ext,
        "source_path": source_path,
    }


def extract_k1(kotor_install: Path, output: Path, k1_version: str) -> dict[str, Any]:
    install = _GameInstall(str(kotor_install), "K1")
    files: list[dict[str, Any]] = []
    for resref in [*SUPERMODEL_RESREFS, *PC_BODY_RESREFS]:
        files.append(_write_resource(install, output, "k1", resref, "mdl", RES_MDL))
        files.append(_write_resource(install, output, "k1", resref, "mdx", RES_MDX))

    source_paths = sorted({item["source_path"] for item in files})
    manifest = {
        "created_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat(),
        "source": "bif_extraction",
        "source_path": source_paths[0] if source_paths else "",
        "source_paths": source_paths,
        "k1_version": k1_version,
        "files": files,
        "purpose": (
            "Isolated stock corpus for GhostRigger retargeter tests. Never touched "
            "by external patchers, override systems, or other projects. Re-extract "
            "from BIF if validation needed."
        ),
        "do_not_modify": True,
    }
    return manifest


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--kotor-install", required=True, help="Path to a KOTOR install containing chitin.key")
    parser.add_argument("--game", choices=["k1"], default="k1", help="Game corpus to extract. Sprint 1 only needs K1.")
    parser.add_argument("--output", default="tests/fixtures/kotor_stock", help="Output corpus root")
    parser.add_argument("--k1-version", default="unknown", help="Version/source note to record in manifest.json")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    kotor_install = Path(args.kotor_install).expanduser().resolve()
    output = Path(args.output).expanduser()
    if not output.is_absolute():
        output = (REPO_ROOT / output).resolve()

    if not (kotor_install / "chitin.key").exists():
        raise SystemExit(f"chitin.key not found under {kotor_install}")

    manifest = extract_k1(kotor_install, output, args.k1_version)
    manifest_path = output / "manifest.json"
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

    print(f"Wrote {len(manifest['files'])} files to {output}")
    print(f"Wrote manifest to {manifest_path}")
    for item in manifest["files"]:
        print(f"  {item['path']}  {item['size_bytes']} bytes  {item['sha256']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
