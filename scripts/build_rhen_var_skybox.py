"""Build the licensed alpine HDR skybox used by the Rhen Var landing zone.

The source is Poly Haven's ``Lago d'Isola`` panorama by Andreas Mischok
(CC0).  KOTOR cannot consume HDR textures directly, so this script projects
the panorama into Ghost Studio's five inward-facing KOTOR sky panels and
tone-maps them to deterministic 1024 px TGA textures.

Run from the repository root:
    py -3.14 scripts/build_rhen_var_skybox.py
"""

from __future__ import annotations

import hashlib
import json
import sys
import tempfile
import urllib.request
from pathlib import Path

from PIL import Image


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.mcp.start_kotormcp_stdio import _python_roots  # noqa: E402


for item in reversed(list(_python_roots(ROOT))):
    if item.exists() and str(item) not in sys.path:
        sys.path.insert(0, str(item))


from src.io.skybox_panorama_conversion import (  # noqa: E402
    PanoramaSkyboxOptions,
    SKYBOX_PANORAMA_FACE_ORDER,
    load_and_convert_equirectangular_panorama,
)


PACK_ROOT = ROOT / "assets" / "map_studio" / "terrain_kits" / "rhen_var"
OUTPUT_ROOT = PACK_ROOT / "skybox"
PROVENANCE_PATH = OUTPUT_ROOT / "provenance.json"
CREDITS_PATH = OUTPUT_ROOT / "CREDITS.md"

SOURCE_PAGE = "https://polyhaven.com/a/lago_disola"
SOURCE_URL = "https://dl.polyhaven.org/file/ph-assets/HDRIs/hdr/4k/lago_disola_4k.hdr"
SOURCE_AUTHOR = "Andreas Mischok"
SOURCE_LICENSE = "CC0 1.0"
SOURCE_MD5 = "a796e3245175b409e675e692beea65f8"
SOURCE_SHA256 = "49b02525462f1e518bc39907277300d38bc611bbbc4703979d7881a9193c882c"

FACE_SIZE = 1024
EXPOSURE_EV = -0.35
LONGITUDE_OFFSET_DEGREES = 18.0
TONE_MAPPER = "aces"
FACE_RESREFS = {
    "north": "gr_rvskyn",
    "east": "gr_rvskye",
    "south": "gr_rvskys",
    "west": "gr_rvskyw",
    "top": "gr_rvskyt",
}


def _hash(path: Path, algorithm: str) -> str:
    digest = hashlib.new(algorithm)
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _download_source(target: Path) -> None:
    request = urllib.request.Request(
        SOURCE_URL,
        headers={"User-Agent": "GhostStudio-RhenVar-Skybox/1.0"},
    )
    with urllib.request.urlopen(request, timeout=90) as response, target.open("wb") as output:
        while True:
            block = response.read(1024 * 1024)
            if not block:
                break
            output.write(block)
    md5 = _hash(target, "md5")
    sha256 = _hash(target, "sha256")
    if md5 != SOURCE_MD5:
        raise RuntimeError(f"Downloaded HDR MD5 differs: {md5} != {SOURCE_MD5}")
    if sha256 != SOURCE_SHA256:
        raise RuntimeError(f"Downloaded HDR SHA-256 differs: {sha256} != {SOURCE_SHA256}")


def main() -> int:
    OUTPUT_ROOT.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="ghostrigger_rhen_var_sky_") as temporary:
        source_path = Path(temporary) / "lago_disola_4k.hdr"
        _download_source(source_path)
        conversion = load_and_convert_equirectangular_panorama(
            source_path,
            options=PanoramaSkyboxOptions(
                face_size=FACE_SIZE,
                exposure_ev=EXPOSURE_EV,
                longitude_offset_degrees=LONGITUDE_OFFSET_DEGREES,
                tone_mapper=TONE_MAPPER,
            ),
        )

    if tuple(face.name for face in conversion.faces) != tuple(SKYBOX_PANORAMA_FACE_ORDER):
        raise RuntimeError("HDR conversion returned an unexpected face order.")

    texture_rows: list[dict[str, object]] = []
    for face in conversion.faces:
        resref = FACE_RESREFS[face.name]
        filename = f"{resref}.tga"
        path = OUTPUT_ROOT / filename
        image = Image.frombytes("RGBA", (face.width, face.height), face.rgba)
        image.save(path, format="TGA", compression=None)
        texture_rows.append(
            {
                "texture_resref": resref,
                "texture_file": f"skybox/{filename}",
                "width": int(face.width),
                "height": int(face.height),
                "packaged_mode": "RGBA",
                "packaged_sha256": _hash(path, "sha256"),
                "skybox_face": face.name,
                "source_kind": "Poly Haven CC0 HDRI",
                "source_asset": "Lago d'Isola",
                "source_author": SOURCE_AUTHOR,
                "source_page": SOURCE_PAGE,
                "source_url": SOURCE_URL,
                "source_license": SOURCE_LICENSE,
                "source_sha256": SOURCE_SHA256,
                "tone_mapper": TONE_MAPPER,
                "exposure_ev": EXPOSURE_EV,
                "longitude_offset_degrees": LONGITUDE_OFFSET_DEGREES,
            }
        )

    provenance = {
        "schema": "ghostrigger.rhen-var-skybox/v1",
        "label": "Rhen Var — Lago d'Isola Alpine Vista",
        "source_asset": "Lago d'Isola",
        "source_author": SOURCE_AUTHOR,
        "source_page": SOURCE_PAGE,
        "source_url": SOURCE_URL,
        "source_license": SOURCE_LICENSE,
        "source_md5": SOURCE_MD5,
        "source_sha256": SOURCE_SHA256,
        "source_packaged": False,
        "projection": "equirectangular_to_five_face_box",
        "face_order": list(SKYBOX_PANORAMA_FACE_ORDER),
        "face_size": FACE_SIZE,
        "exposure_ev": EXPOSURE_EV,
        "longitude_offset_degrees": LONGITUDE_OFFSET_DEGREES,
        "tone_mapper": TONE_MAPPER,
        "textures": texture_rows,
    }
    PROVENANCE_PATH.write_text(
        json.dumps(provenance, indent=2, sort_keys=False) + "\n",
        encoding="utf-8",
    )
    CREDITS_PATH.write_text(
        "# Rhen Var Alpine Skybox Credits\n\n"
        "- Source: [Lago d'Isola](https://polyhaven.com/a/lago_disola)\n"
        f"- Creator: {SOURCE_AUTHOR}\n"
        "- License: [CC0 1.0](https://creativecommons.org/publicdomain/zero/1.0/)\n"
        "- Adaptation: projected and ACES tone-mapped into five KOTOR-oriented "
        "skybox faces by Ghost Studio.\n"
        "- The original HDR is referenced by URL and digest but is not repackaged; "
        "the derived KOTOR TGA faces are included.\n",
        encoding="utf-8",
    )
    print(json.dumps(provenance, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
