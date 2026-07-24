"""Source-preserving texture inspection and output policy for Head Builder.

This IO owner separates source bytes, decoded preview facts, TXI sampler
policy, and eventual package names.  It does not upload renderer resources or
mutate a game installation.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
from io import BytesIO
from pathlib import Path
import re
from typing import Any, Mapping


MAX_HEAD_TEXTURE_BYTES = 64 * 1024 * 1024
MAX_TXI_BYTES = 64 * 1024
HEAD_TEXTURE_FORMATS = frozenset({"TGA", "TPC"})
HEAD_TEXTURE_ALPHA_MODES = frozenset(
    {"opaque", "blend", "punchthrough"}
)
HEAD_TXI_DELIVERY = frozenset({"none", "sidecar", "embedded"})
_RESREF_RE = re.compile(r"^[A-Za-z0-9_]{1,16}$")


class HeadTextureError(ValueError):
    """Raised when texture bytes or package policy are unsafe."""


@dataclass(frozen=True, slots=True)
class HeadTextureAsset:
    source_path: str
    source_format: str
    source_resref: str
    source_size_bytes: int
    source_sha256: str
    width: int
    height: int
    mipmap_count: int
    pixel_format: str
    power_of_two: bool
    has_alpha: bool
    alpha_min: int
    alpha_max: int
    decoded_rgba_sha256: str
    txi_origin: str = "none"
    txi_path: str = ""
    txi_sha256: str = ""
    txi_properties: Mapping[str, Any] = field(default_factory=dict)
    warnings: tuple[str, ...] = ()

    @property
    def accepted(self) -> bool:
        return (
            self.source_format in HEAD_TEXTURE_FORMATS
            and self.width > 0
            and self.height > 0
            and self.power_of_two
            and bool(self.source_sha256)
            and bool(self.decoded_rgba_sha256)
        )

    def project_facts(self) -> dict[str, Any]:
        return {
            "schema": "ghostrigger.head_texture_asset",
            "version": 1,
            "accepted": self.accepted,
            "source_path": self.source_path,
            "source_format": self.source_format,
            "source_resref": self.source_resref,
            "source_size_bytes": self.source_size_bytes,
            "source_sha256": self.source_sha256,
            "width": self.width,
            "height": self.height,
            "mipmap_count": self.mipmap_count,
            "pixel_format": self.pixel_format,
            "power_of_two": self.power_of_two,
            "has_alpha": self.has_alpha,
            "alpha_min": self.alpha_min,
            "alpha_max": self.alpha_max,
            "decoded_rgba_sha256": self.decoded_rgba_sha256,
            "txi_origin": self.txi_origin,
            "txi_path": self.txi_path,
            "txi_sha256": self.txi_sha256,
            "txi_properties": dict(self.txi_properties),
            "warnings": list(self.warnings),
        }


@dataclass(frozen=True, slots=True)
class HeadTextureOutputPolicy:
    source_sha256: str
    output_resref: str
    output_format: str
    txi_delivery: str
    alpha_mode: str
    environment_map_resref: str
    bumpmap_resref: str
    clamp_s: bool
    clamp_t: bool
    mipmap: bool
    preserve_source_txi: bool
    warnings: tuple[str, ...] = ()

    @property
    def accepted(self) -> bool:
        return (
            valid_head_texture_resref(self.output_resref)
            and self.output_format in HEAD_TEXTURE_FORMATS
            and self.txi_delivery in HEAD_TXI_DELIVERY
            and self.alpha_mode in HEAD_TEXTURE_ALPHA_MODES
            and (
                not self.environment_map_resref
                or valid_head_texture_resref(self.environment_map_resref)
            )
            and (
                not self.bumpmap_resref
                or valid_head_texture_resref(self.bumpmap_resref)
            )
            and (
                self.output_format != "TPC"
                or self.txi_delivery != "sidecar"
            )
            and (
                self.output_format != "TGA"
                or self.txi_delivery != "embedded"
            )
        )

    @property
    def packaged_files(self) -> tuple[str, ...]:
        extension = self.output_format.lower()
        rows = [f"{self.output_resref}.{extension}"]
        if self.txi_delivery == "sidecar":
            rows.append(f"{self.output_resref}.txi")
        return tuple(rows)

    def txi_text(self) -> str:
        rows: list[str] = []
        if self.alpha_mode == "blend":
            rows.append("blending additive")
        elif self.alpha_mode == "punchthrough":
            rows.append("blending punchthrough")
        if self.environment_map_resref:
            rows.append(
                f"envmaptexture {self.environment_map_resref.lower()}"
            )
        if self.bumpmap_resref:
            rows.append(f"bumpmaptexture {self.bumpmap_resref.lower()}")
        clamp = (1 if self.clamp_s else 0) | (2 if self.clamp_t else 0)
        if clamp:
            rows.append(f"clamp {clamp}")
        rows.append(f"mipmap {1 if self.mipmap else 0}")
        return "\n".join(rows) + "\n"

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": "ghostrigger.head_texture_output_policy",
            "version": 1,
            "accepted": self.accepted,
            "source_sha256": self.source_sha256,
            "output_resref": self.output_resref,
            "output_format": self.output_format,
            "txi_delivery": self.txi_delivery,
            "alpha_mode": self.alpha_mode,
            "environment_map_resref": self.environment_map_resref,
            "bumpmap_resref": self.bumpmap_resref,
            "clamp_s": self.clamp_s,
            "clamp_t": self.clamp_t,
            "mipmap": self.mipmap,
            "preserve_source_txi": self.preserve_source_txi,
            "packaged_files": list(self.packaged_files),
            "generated_txi_sha256": hashlib.sha256(
                self.txi_text().encode("ascii")
            ).hexdigest(),
            "warnings": list(self.warnings),
        }


def inspect_head_texture(
    path: str | Path,
    *,
    txi_path: str | Path | None = None,
    maximum_bytes: int = MAX_HEAD_TEXTURE_BYTES,
) -> HeadTextureAsset:
    """Fingerprint and decode TGA/TPC source bytes without renderer state."""

    source = Path(path).expanduser().resolve()
    if not source.is_file():
        raise HeadTextureError(f"Head texture does not exist: {source}")
    source_format = source.suffix.lstrip(".").upper()
    if source_format not in HEAD_TEXTURE_FORMATS:
        raise HeadTextureError("Head textures must be TGA or TPC")
    size = source.stat().st_size
    if size <= 0 or size > int(maximum_bytes):
        raise HeadTextureError(
            f"Head texture size must be 1..{int(maximum_bytes)} bytes"
        )
    data = source.read_bytes()
    source_sha = hashlib.sha256(data).hexdigest()
    if source_format == "TGA":
        (
            width,
            height,
            mipmaps,
            pixel_format,
            rgba,
            embedded_txi,
        ) = _decode_tga(data)
    else:
        (
            width,
            height,
            mipmaps,
            pixel_format,
            rgba,
            embedded_txi,
        ) = _decode_tpc(data)
    alpha = rgba[3::4]
    alpha_min = min(alpha) if alpha else 255
    alpha_max = max(alpha) if alpha else 255
    has_alpha = alpha_min < 255
    sidecar = (
        Path(txi_path).expanduser().resolve()
        if txi_path is not None
        else source.with_suffix(".txi")
    )
    txi_origin = "none"
    txi_source_path = ""
    txi_text = ""
    if sidecar.is_file():
        txi_bytes = sidecar.read_bytes()
        if len(txi_bytes) > MAX_TXI_BYTES:
            raise HeadTextureError("TXI sidecar exceeds the safety limit")
        txi_text = txi_bytes.decode("ascii", errors="strict")
        txi_origin = "sidecar"
        txi_source_path = str(sidecar)
    elif embedded_txi.strip():
        txi_text = embedded_txi
        txi_origin = "embedded"
    txi_sha = (
        hashlib.sha256(txi_text.encode("ascii")).hexdigest()
        if txi_text
        else ""
    )
    warnings: list[str] = []
    power_of_two = _power_of_two(width) and _power_of_two(height)
    if not power_of_two:
        warnings.append(
            "KOTOR head texture dimensions must be powers of two"
        )
    if not has_alpha and _parse_txi(txi_text).get("blending"):
        warnings.append(
            "TXI requests blending but the decoded texture is fully opaque"
        )
    return HeadTextureAsset(
        source_path=str(source),
        source_format=source_format,
        source_resref=source.stem,
        source_size_bytes=size,
        source_sha256=source_sha,
        width=width,
        height=height,
        mipmap_count=mipmaps,
        pixel_format=pixel_format,
        power_of_two=power_of_two,
        has_alpha=has_alpha,
        alpha_min=alpha_min,
        alpha_max=alpha_max,
        decoded_rgba_sha256=hashlib.sha256(rgba).hexdigest(),
        txi_origin=txi_origin,
        txi_path=txi_source_path,
        txi_sha256=txi_sha,
        txi_properties=_parse_txi(txi_text),
        warnings=tuple(warnings),
    )


def build_head_texture_output_policy(
    asset: HeadTextureAsset,
    *,
    output_resref: str,
    output_format: str,
    txi_delivery: str = "auto",
    alpha_mode: str = "opaque",
    environment_map_resref: str = "",
    bumpmap_resref: str = "",
    clamp_s: bool = False,
    clamp_t: bool = False,
    mipmap: bool = True,
    preserve_source_txi: bool = True,
) -> HeadTextureOutputPolicy:
    if not isinstance(asset, HeadTextureAsset):
        raise TypeError("asset must be HeadTextureAsset")
    if not asset.accepted:
        raise HeadTextureError(
            "Texture source must pass dimensions and decode checks"
        )
    format_name = str(output_format or "").strip().upper()
    delivery = str(txi_delivery or "").strip().lower()
    if delivery == "auto":
        delivery = "embedded" if format_name == "TPC" else "sidecar"
    alpha = str(alpha_mode or "").strip().lower()
    policy = HeadTextureOutputPolicy(
        source_sha256=asset.source_sha256,
        output_resref=str(output_resref or "").strip(),
        output_format=format_name,
        txi_delivery=delivery,
        alpha_mode=alpha,
        environment_map_resref=str(environment_map_resref or "").strip(),
        bumpmap_resref=str(bumpmap_resref or "").strip(),
        clamp_s=bool(clamp_s),
        clamp_t=bool(clamp_t),
        mipmap=bool(mipmap),
        preserve_source_txi=bool(preserve_source_txi),
        warnings=(
            (
                "The selected alpha mode uses an opaque source texture"
            ,)
            if alpha != "opaque" and not asset.has_alpha
            else ()
        ),
    )
    if not policy.accepted:
        raise HeadTextureError(
            "Texture output requires a valid <=16 character ResRef, "
            "TGA/TPC format, compatible TXI delivery, and valid metadata ResRefs"
        )
    return policy


def valid_head_texture_resref(value: str) -> bool:
    return bool(_RESREF_RE.fullmatch(str(value or "").strip()))


def _decode_tga(
    data: bytes,
) -> tuple[int, int, int, str, bytes, str]:
    try:
        from PIL import Image

        with Image.open(BytesIO(data)) as image:
            if str(image.format or "").upper() != "TGA":
                raise HeadTextureError("The .tga file is not a TGA image")
            rgba_image = image.convert("RGBA")
            return (
                int(rgba_image.width),
                int(rgba_image.height),
                1,
                "RGBA8",
                bytes(rgba_image.tobytes("raw", "RGBA")),
                "",
            )
    except HeadTextureError:
        raise
    except Exception as exc:
        raise HeadTextureError(f"Unable to decode TGA texture: {exc}") from exc


def _decode_tpc(
    data: bytes,
) -> tuple[int, int, int, str, bytes, str]:
    try:
        from PIL import Image
        from pykotor.resource.formats.tpc import read_tpc
        from pykotor.resource.formats.tpc.tpc_data import TPCTextureFormat

        texture = read_tpc(bytes(data))
        dimensions = tuple(int(value) for value in texture.dimensions())
        mipmaps = tuple(texture.layers[0].mipmaps) if texture.layers else ()
        if len(dimensions) != 2 or not mipmaps:
            raise HeadTextureError("TPC texture has no decodable mipmaps")
        original_format = texture.format()
        working = mipmaps[0].copy()
        working.convert(TPCTextureFormat.RGBA)
        image = working.to_pil_image()
        if image is None:
            raise HeadTextureError("PyKotor could not decode the TPC image")
        if image.mode != "RGBA":
            image = image.convert("RGBA")
        compressed = original_format in {
            TPCTextureFormat.DXT1,
            TPCTextureFormat.DXT3,
            TPCTextureFormat.DXT5,
        }
        if not compressed:
            transpose = getattr(Image, "Transpose", Image)
            image = image.transpose(transpose.FLIP_TOP_BOTTOM)
        return (
            dimensions[0],
            dimensions[1],
            len(mipmaps),
            str(getattr(original_format, "name", original_format)),
            bytes(image.tobytes("raw", "RGBA")),
            str(getattr(texture, "txi", "") or ""),
        )
    except HeadTextureError:
        raise
    except Exception as exc:
        raise HeadTextureError(f"Unable to decode TPC texture: {exc}") from exc


def _parse_txi(text: str) -> dict[str, Any]:
    properties: dict[str, Any] = {}
    for raw_line in str(text or "").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        key, _, value = line.partition(" ")
        normalized = key.casefold()
        argument = value.strip()
        if normalized in {"clamp", "mipmap", "numx", "numy"}:
            try:
                properties[normalized] = int(argument)
            except ValueError:
                properties[normalized] = argument.casefold()
        elif normalized in {"fps", "bumpmapscaling"}:
            try:
                properties[normalized] = float(argument)
            except ValueError:
                properties[normalized] = argument.casefold()
        else:
            properties[normalized] = argument.casefold()
    return properties


def _power_of_two(value: int) -> bool:
    return value > 0 and (value & (value - 1)) == 0


__all__ = [
    "HEAD_TEXTURE_ALPHA_MODES",
    "HEAD_TEXTURE_FORMATS",
    "HEAD_TXI_DELIVERY",
    "HeadTextureAsset",
    "HeadTextureError",
    "HeadTextureOutputPolicy",
    "build_head_texture_output_policy",
    "inspect_head_texture",
    "valid_head_texture_resref",
]
