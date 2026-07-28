"""Focused source, TXI, and package-policy tests for Head Builder textures."""

from __future__ import annotations

from pathlib import Path

from PIL import Image
import pytest

from src.io.head_texture_asset import (
    HeadTextureError,
    build_head_texture_output_policy,
    inspect_head_texture,
    valid_head_texture_resref,
)
from src.io.head_builder_package import _texture_outputs


def _write_tga(path: Path, size: tuple[int, int] = (4, 4)) -> None:
    image = Image.new("RGBA", size, (32, 64, 96, 255))
    image.putpixel((0, 0), (255, 0, 0, 64))
    image.save(path, format="TGA")


def _write_png(path: Path, size: tuple[int, int] = (4, 4)) -> None:
    image = Image.new("RGBA", size, (32, 64, 96, 255))
    image.putpixel((0, 0), (255, 0, 0, 64))
    image.save(path, format="PNG")


def _write_tpc(path: Path) -> None:
    from pykotor.resource.formats.tpc.tpc_auto import bytes_tpc
    from pykotor.resource.formats.tpc.tpc_data import TPC, TPCTextureFormat
    from pykotor.resource.type import ResourceType

    rgba = bytes((20, 40, 60, 255)) * 16
    texture = TPC()
    texture.set_single(rgba, TPCTextureFormat.RGBA, 4, 4)
    texture.layers[0].mipmaps[:] = texture.layers[0].mipmaps[:1]
    path.write_bytes(
        bytes_tpc(texture, ResourceType.TPC)
        + b"mipmap 0\nenvmaptexture CM_Baremetal\n"
    )


def test_tga_inspection_preserves_source_and_txi_facts(tmp_path: Path) -> None:
    texture_path = tmp_path / "hero_face.tga"
    txi_path = tmp_path / "hero_face.txi"
    _write_tga(texture_path)
    txi_path.write_text(
        "blending punchthrough\nclamp 3\nmipmap 1\n",
        encoding="ascii",
    )

    asset = inspect_head_texture(texture_path)

    assert asset.accepted
    assert (asset.width, asset.height) == (4, 4)
    assert asset.has_alpha
    assert asset.alpha_min == 64
    assert asset.alpha_max == 255
    assert asset.txi_origin == "sidecar"
    assert asset.txi_properties["blending"] == "punchthrough"
    assert asset.txi_properties["clamp"] == 3
    assert asset.project_facts()["source_sha256"] == asset.source_sha256


def test_tpc_inspection_reads_mipmap_and_embedded_txi(tmp_path: Path) -> None:
    texture_path = tmp_path / "hero_face.tpc"
    _write_tpc(texture_path)

    asset = inspect_head_texture(texture_path)

    assert asset.accepted
    assert asset.source_format == "TPC"
    assert (asset.width, asset.height) == (4, 4)
    assert asset.mipmap_count == 1
    assert asset.txi_origin == "embedded"
    assert asset.txi_properties["mipmap"] == 0
    assert asset.txi_properties["envmaptexture"] == "cm_baremetal"


def test_png_source_is_converted_to_retail_tga_without_source_rewrite(
    tmp_path: Path,
) -> None:
    texture_path = tmp_path / "hero_face.png"
    _write_png(texture_path)
    source_bytes = texture_path.read_bytes()
    asset = inspect_head_texture(texture_path)
    policy = build_head_texture_output_policy(
        asset,
        output_resref="P_CDH01",
        output_format="TGA",
        txi_delivery="sidecar",
    )

    outputs = _texture_outputs(asset, policy)

    assert asset.accepted
    assert asset.source_format == "PNG"
    assert set(outputs) == {"P_CDH01.tga", "P_CDH01.txi"}
    retail_tga = outputs["P_CDH01.tga"]
    assert retail_tga[17] & 0x20 == 0
    with Image.open(__import__("io").BytesIO(retail_tga)) as image:
        assert image.size == (4, 4)
        assert image.convert("RGBA").getpixel((0, 0)) == (255, 0, 0, 64)
    assert texture_path.read_bytes() == source_bytes


def test_non_power_of_two_texture_is_not_export_eligible(
    tmp_path: Path,
) -> None:
    texture_path = tmp_path / "bad_size.tga"
    _write_tga(texture_path, (3, 4))

    asset = inspect_head_texture(texture_path)

    assert not asset.accepted
    assert not asset.power_of_two
    with pytest.raises(HeadTextureError, match="dimensions"):
        build_head_texture_output_policy(
            asset,
            output_resref="P_CDH01",
            output_format="TGA",
        )


def test_output_policy_lists_package_files_and_deterministic_txi(
    tmp_path: Path,
) -> None:
    texture_path = tmp_path / "hero_face.tga"
    _write_tga(texture_path)
    asset = inspect_head_texture(texture_path)

    policy = build_head_texture_output_policy(
        asset,
        output_resref="P_CDH01",
        output_format="TGA",
        txi_delivery="sidecar",
        alpha_mode="punchthrough",
        environment_map_resref="CM_Baremetal",
        clamp_s=True,
        clamp_t=True,
        mipmap=True,
    )

    assert policy.accepted
    assert policy.packaged_files == ("P_CDH01.tga", "P_CDH01.txi")
    assert policy.txi_text() == (
        "blending punchthrough\n"
        "envmaptexture cm_baremetal\n"
        "clamp 3\n"
        "mipmap 1\n"
    )


def test_tpc_policy_requires_embedded_or_no_txi(tmp_path: Path) -> None:
    texture_path = tmp_path / "hero_face.tga"
    _write_tga(texture_path)
    asset = inspect_head_texture(texture_path)

    with pytest.raises(HeadTextureError, match="compatible TXI"):
        build_head_texture_output_policy(
            asset,
            output_resref="P_CDH01",
            output_format="TPC",
            txi_delivery="sidecar",
        )


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("P_CDH01", True),
        ("1234567890123456", True),
        ("", False),
        ("seventeen_chars___", False),
        ("bad name", False),
        ("bad-name", False),
    ],
)
def test_texture_resrefs_use_odyssey_field_contract(
    value: str,
    expected: bool,
) -> None:
    assert valid_head_texture_resref(value) is expected
