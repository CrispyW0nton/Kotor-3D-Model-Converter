"""Texture preview helpers for stock KotOR module archives."""

from __future__ import annotations

from dataclasses import dataclass
from io import BytesIO
from pathlib import Path
from typing import Callable


@dataclass(frozen=True)
class ModuleTexturePreview:
    label: str
    source_format: str
    width: int
    height: int
    preview_width: int
    preview_height: int
    rgba: bytes
    txi: str = ""


@dataclass(frozen=True)
class ModuleTextureLibraryResource:
    resref: str
    restype: str
    restype_id: int
    size: int = 0
    source: str = "game library"
    game: str = ""
    data_loader: Callable[[], bytes | None] | None = None

    @property
    def label(self) -> str:
        return f"{self.resref}.{self.restype}"

    def read_bytes(self) -> bytes:
        if self.data_loader is None:
            return b""
        return bytes(self.data_loader() or b"")


@dataclass(frozen=True)
class ModuleTextureFileResource:
    resref: str
    restype: str
    restype_id: int
    path: str
    size: int = 0
    source: str = "imported texture"

    @property
    def label(self) -> str:
        return f"{self.resref}.{self.restype}"

    def read_bytes(self) -> bytes:
        return Path(self.path).read_bytes()


@dataclass(frozen=True)
class ModuleTextureMemoryResource:
    resref: str
    restype: str
    restype_id: int
    payload: bytes
    source_label: str = "edited texture"
    source: str = "edited texture"

    @property
    def label(self) -> str:
        return f"{self.resref}.{self.restype}"

    @property
    def size(self) -> int:
        return len(self.payload)

    def read_bytes(self) -> bytes:
        return bytes(self.payload)


def decode_module_texture_preview(
    data: bytes,
    *,
    restype: str,
    label: str,
    max_size: int = 96,
) -> ModuleTexturePreview | None:
    """Decode a module-local texture to thumbnail-sized RGBA bytes."""

    restype = str(restype or "").lower().lstrip(".")
    if restype not in {"tga", "tpc"} or not data:
        return None
    try:
        from PIL import Image

        image = None
        txi = ""
        if restype == "tga":
            image = Image.open(BytesIO(data)).convert("RGBA")
        elif restype == "tpc":
            from src.core.graphics.tpc import _load_tpc_bytes

            image = _load_tpc_bytes(data)
            txi = str(getattr(image, "_txi_str", "") or "") if image is not None else ""
            if image is not None and bool(getattr(image, "_gr_gpu_uv_v_flip", False)):
                image = image.transpose(Image.FLIP_TOP_BOTTOM)
            if image is not None and image.mode != "RGBA":
                image = image.convert("RGBA")
        if image is None:
            return None
        width, height = image.size
        preview = image.copy()
        preview.thumbnail((max(16, int(max_size)), max(16, int(max_size))), Image.LANCZOS)
        if preview.mode != "RGBA":
            preview = preview.convert("RGBA")
        preview_width, preview_height = preview.size
        return ModuleTexturePreview(
            label=label,
            source_format=restype,
            width=int(width),
            height=int(height),
            preview_width=int(preview_width),
            preview_height=int(preview_height),
            rgba=preview.tobytes("raw", "RGBA"),
            txi=txi,
        )
    except Exception:
        return None
