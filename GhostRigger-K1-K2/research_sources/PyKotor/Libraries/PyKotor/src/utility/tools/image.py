from __future__ import annotations

import os
import pathlib

from typing import TYPE_CHECKING

from loggerplus import RobustLogger
from utility.gui.qt.tools.image import _process_pil_image, _process_qt_image, _process_tpc_image
from utility.misc import get_normalized_extension

if TYPE_CHECKING:
    from typing_extensions import Literal


def image_from_file(
    filepath: os.PathLike | str,
    mipmap: int = 64,
    img_format: Literal["RGBA", "RGB", "RGBX", "BGR", "BGRA", "Default"] = "RGBA",
) -> tuple[int, int, bytes]:
    filepath_obj = pathlib.Path(os.path.normpath(filepath))

    try:
        result = _process_qt_image(filepath_obj, mipmap)
        if result:
            return result
    except ImportError:
        RobustLogger().warning(f"Qt not available for resource type: {get_normalized_extension(filepath_obj)!r}")

    try:
        result = _process_pil_image(filepath_obj, mipmap, img_format)
        if result:
            return result
    except ImportError:
        RobustLogger().warning(f"Pillow not available for resource type: {get_normalized_extension(filepath_obj)!r}")

    try:
        result = _process_tpc_image(filepath_obj, mipmap)
        if result:
            return result
    except ImportError:
        RobustLogger().warning(f"PyKotor not available for resource type: {get_normalized_extension(filepath_obj)!r}")

    raise ValueError(f"No suitable image processing library available for resource type: {get_normalized_extension(filepath_obj)!r}")
