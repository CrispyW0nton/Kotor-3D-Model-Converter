"""Small non-destructive TGA adjustment drafts for stock Module Editor textures."""

from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO


@dataclass(frozen=True)
class ModuleTgaEditDraft:
    source_resref: str
    source_label: str
    output_resref: str
    width: int = 0
    height: int = 0
    brightness: int = 0
    contrast: int = 0
    snow: int = 0
    output_payload: bytes = b""
    validation_status: str = "not_validated"
    issues: tuple[str, ...] = ()
    status: str = "preview_only"

    @property
    def ready(self) -> bool:
        return bool(self.output_payload) and self.validation_status == "valid"

    @property
    def label(self) -> str:
        return f"{self.output_resref}.tga"

    @property
    def summary(self) -> str:
        return (
            f"{self.source_resref}.tga -> {self.output_resref}.tga "
            f"(brightness {self.brightness:+d}, contrast {self.contrast:+d}, snow {self.snow})"
        )


def create_tga_adjustment_draft(
    source_payload: bytes,
    *,
    source_resref: str,
    source_label: str,
    output_resref: str = "",
    brightness: int = 0,
    contrast: int = 0,
    snow: int = 0,
) -> ModuleTgaEditDraft:
    """Create an edited TGA payload without writing files or touching source data."""

    source_resref = _clean_resref(source_resref)
    output_resref = _clean_resref(output_resref) or _default_output_resref(source_resref)
    brightness = _clamp_int(brightness, -100, 100)
    contrast = _clamp_int(contrast, -100, 100)
    snow = _clamp_int(snow, 0, 100)
    issue = _resref_issue(output_resref)
    if issue:
        return _tga_edit_error(source_resref, source_label, output_resref, brightness, contrast, snow, "invalid_resref", issue)
    if not source_payload:
        return _tga_edit_error(source_resref, source_label, output_resref, brightness, contrast, snow, "missing_payload", "Source TGA payload is empty.")
    try:
        from PIL import Image, ImageEnhance, ImageOps

        image = Image.open(BytesIO(source_payload)).convert("RGBA")
        width, height = image.size
        if brightness:
            image = ImageEnhance.Brightness(image).enhance(max(0.0, 1.0 + brightness / 100.0))
        if contrast:
            image = ImageEnhance.Contrast(image).enhance(max(0.0, 1.0 + contrast / 100.0))
        if snow:
            alpha = snow / 100.0
            pale = Image.new("RGBA", image.size, (224, 238, 255, 255))
            desaturated = ImageOps.grayscale(image).convert("RGBA")
            image = Image.blend(image, desaturated, min(0.55, alpha * 0.55))
            image = Image.blend(image, pale, min(0.70, alpha * 0.70))
        output = BytesIO()
        image.save(output, format="TGA")
        payload = output.getvalue()
        check = Image.open(BytesIO(payload)).convert("RGBA")
        if check.size != (width, height):
            return _tga_edit_error(source_resref, source_label, output_resref, brightness, contrast, snow, "roundtrip_failed", "Edited TGA dimensions changed during write/read validation.")
        return ModuleTgaEditDraft(
            source_resref=source_resref,
            source_label=source_label,
            output_resref=output_resref,
            width=int(width),
            height=int(height),
            brightness=brightness,
            contrast=contrast,
            snow=snow,
            output_payload=payload,
            validation_status="valid",
        )
    except Exception as exc:
        return _tga_edit_error(source_resref, source_label, output_resref, brightness, contrast, snow, "decode_failed", str(exc))


def _tga_edit_error(
    source_resref: str,
    source_label: str,
    output_resref: str,
    brightness: int,
    contrast: int,
    snow: int,
    status: str,
    issue: str,
) -> ModuleTgaEditDraft:
    return ModuleTgaEditDraft(
        source_resref=source_resref,
        source_label=source_label,
        output_resref=output_resref,
        brightness=brightness,
        contrast=contrast,
        snow=snow,
        validation_status=status,
        issues=(issue,),
    )


def _clean_resref(value: object) -> str:
    return str(value or "").strip().strip("\x00").lower()


def _default_output_resref(source_resref: str) -> str:
    base = _clean_resref(source_resref) or "edited_tga"
    suffix = "_snow"
    if len(base) + len(suffix) <= 16:
        return f"{base}{suffix}"
    return f"{base[:16 - len(suffix)]}{suffix}"


def _resref_issue(value: str) -> str:
    if not value:
        return "Output texture ResRef cannot be empty."
    if len(value) > 16:
        return "Output texture ResRef exceeds the 16-character KotOR limit."
    try:
        value.encode("ascii")
    except UnicodeEncodeError:
        return "Output texture ResRef must be ASCII."
    if not all(character.isalnum() or character == "_" for character in value):
        return "Output texture ResRef may only contain letters, numbers, and underscores."
    return ""


def _clamp_int(value: object, minimum: int, maximum: int) -> int:
    try:
        number = int(value)
    except Exception:
        number = 0
    return max(minimum, min(maximum, number))


__all__ = [
    "ModuleTgaEditDraft",
    "create_tga_adjustment_draft",
]
