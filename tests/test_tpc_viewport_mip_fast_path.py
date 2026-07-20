from __future__ import annotations

import struct
import sys
from io import BytesIO
from pathlib import Path

import pytest


ROOT = Path(__file__).resolve().parents[1]
K2_ROOT = Path(r"C:\Program Files (x86)\Steam\steamapps\common\Knights of the Old Republic II")


def _configure_python_roots() -> None:
    from scripts.mcp.start_kotormcp_stdio import _python_roots

    for item in reversed(_python_roots(ROOT)):
        text = str(item)
        if item.exists() and text not in sys.path:
            sys.path.insert(0, text)


_configure_python_roots()


@pytest.fixture(scope="module")
def installation():
    if not K2_ROOT.is_dir():
        pytest.skip("K2 installation is unavailable")
    from pykotor.extract.installation import Installation

    return Installation(K2_ROOT)


def _raw_tpc(installation, resref: str) -> bytes:
    from pykotor.resource.type import ResourceType

    resource = installation.resource(resref, ResourceType.TPC)
    assert resource is not None, resref
    return bytes(resource.data)


def _authority_selected_mip(raw: bytes, max_size: int):
    from PIL import Image
    from pykotor.resource.formats.tpc import read_tpc
    from pykotor.resource.formats.tpc.tpc_data import TPCTextureFormat

    tpc = read_tpc(raw)
    original_format = tpc.format()
    mipmaps = tpc.layers[0].mipmaps
    index = next(
        (index for index, mip in enumerate(mipmaps) if max(mip.width, mip.height) <= max_size),
        len(mipmaps) - 1,
    )
    mip = mipmaps[index].copy()
    mip.convert(TPCTextureFormat.RGBA)
    image = mip.to_pil_image().convert("RGBA")
    if original_format in {TPCTextureFormat.DXT1, TPCTextureFormat.DXT3, TPCTextureFormat.DXT5}:
        image = image.transpose(Image.Transpose.FLIP_TOP_BOTTOM)
    return tpc, index, image


@pytest.mark.parametrize(
    ("resref", "format_name", "source_size", "mip_level", "output_size"),
    (
        ("tel_ja11", "DXT1", (2048, 2048), 2, (512, 512)),
        ("tel_hw10", "DXT5", (4096, 4096), 3, (512, 512)),
        ("207tel_1_lm0", "RGBA", (128, 128), 0, (128, 128)),
    ),
)
def test_viewport_decode_matches_direct_pykotor_selected_mip(
    installation,
    resref: str,
    format_name: str,
    source_size: tuple[int, int],
    mip_level: int,
    output_size: tuple[int, int],
) -> None:
    from src.core.graphics.tpc import _load_tpc_bytes

    raw = _raw_tpc(installation, resref)
    tpc, expected_level, authority = _authority_selected_mip(raw, 512)
    image = _load_tpc_bytes(raw, max_size=512)

    assert image is not None
    assert tpc.format().name == format_name
    assert tpc.dimensions() == source_size
    assert expected_level == mip_level
    assert image.size == output_size
    assert image.mode == "RGBA"
    assert image.tobytes() == authority.tobytes()
    assert image._tpc_source_size == source_size
    assert image._tpc_mip_level == mip_level
    assert image._tpc_mip_size == output_size
    assert image._tpc_viewport_max_size == 512
    assert image._gr_gpu_uv_v_flip is True
    assert image._tpc_raw == raw
    assert image._txi_str == str(tpc.txi or "").strip()
    alpha_test = struct.unpack_from("<f", raw, 4)[0]
    assert image._txi_alpha_test == pytest.approx(alpha_test)


def test_default_loader_preserves_full_resolution_contract(installation) -> None:
    from PIL import Image
    from pykotor.resource.formats.tpc import read_tpc
    from pykotor.resource.formats.tpc.tpc_data import TPCTextureFormat
    from src.core.graphics.tpc import _load_tpc_bytes

    raw = _raw_tpc(installation, "plc_chair1")
    tpc = read_tpc(raw)
    tpc.convert(TPCTextureFormat.RGBA)
    authority = tpc.get(0, 0).to_pil_image().convert("RGBA").transpose(Image.Transpose.FLIP_TOP_BOTTOM)
    image = _load_tpc_bytes(raw)

    assert image is not None
    assert image.size == (512, 512)
    assert image.tobytes() == authority.tobytes()
    assert image._tpc_mip_level == 0
    assert image._tpc_viewport_max_size is None


def test_texture_cache_uses_authored_mip_and_preserves_alpha_metadata(installation) -> None:
    from src.core.graphics.txi import _parse_txi_string
    from src.core.rendering.frame_core.texture_cache import TextureCache

    raw = _raw_tpc(installation, "n_commf01")
    cache = TextureCache()
    image = cache._load_bytes(raw)
    assert image is not None
    assert image.size == (512, 512)
    assert image._tpc_source_size == (1024, 1024)
    assert image._tpc_mip_level == 1
    assert image._tpc_raw == raw
    assert image._txi_str == ""
    assert image._txi_alpha_test == pytest.approx(1.0)

    processed = cache._apply_kotor_alpha(raw, image, _parse_txi_string(image._txi_str))
    assert processed.size == image.size
    assert processed._tpc_source_size == (1024, 1024)
    assert processed._tpc_mip_level == 1
    assert processed._tpc_raw == raw
    assert processed._txi_alpha_test == pytest.approx(1.0)


def test_texture_cache_normalizes_loose_tga_for_kotor_uv_sampling() -> None:
    from PIL import Image
    from src.core.rendering.frame_core.texture_cache import TextureCache

    # Source/Pillow row order is top-down: red+green above blue+yellow.
    source = Image.new("RGBA", (2, 2))
    source.putdata(
        (
            (255, 0, 0, 255),
            (0, 255, 0, 255),
            (0, 0, 255, 255),
            (255, 255, 0, 255),
        )
    )
    encoded = BytesIO()
    source.save(encoded, format="TGA")

    image = TextureCache()._load_bytes(encoded.getvalue())

    assert image is not None
    # GPU upload rows are bottom-up after normalization.
    assert tuple(image.get_flattened_data()) == (
        (0, 0, 255, 255),
        (255, 255, 0, 255),
        (255, 0, 0, 255),
        (0, 255, 0, 255),
    )
    # KOTOR binary UV V=0 means top, so the shader must convert it to GL V=1.
    # Imported DCC nodes remain correct because they carry uv_v_flip=False.
    assert image._gr_gpu_uv_v_flip is True
