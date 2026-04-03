"""GLM compatibility layer using PyKotor geometry classes.

This module provides a PyGLM-compatible API by aliasing PyKotor's geometry classes
and utility functions. It supports PyPy and works without PyGLM.

Note: All classes intentionally use lowercase names to match PyGLM's API.
"""

from __future__ import annotations

import importlib
import math

from typing import TYPE_CHECKING

# Import GLM-compatible functions
from pykotor.common.geometry_utils import (
    cross,
    decompose,
    eulerAngles,
    inverse,
    length,
    mat4_cast,
    normalize,
    perspective,
    rotate,
    translate,
    unProject,
    value_ptr,
)

# Import geometry classes and alias to lowercase (GLM-compatible names)
from utility.common.geometry import Matrix4, Vector2, Vector3, Vector4

# GLM-compatible aliases (lowercase)
vec2 = Vector2  # noqa: N801
vec3 = Vector3  # noqa: N801
vec4 = Vector4  # noqa: N801
mat4 = Matrix4  # noqa: N801


def quat(*args) -> Vector4:  # noqa: N802
    """Create a quaternion stored as Vector4, with PyGLM-compatible constructor.

    PyGLM convention: quat(w, x, y, z) where w is the FIRST argument.
    Vector4 convention: Vector4(x, y, z, w) where w is the LAST argument.

    This function bridges the gap so that quat(w, x, y, z) correctly stores
    the quaternion components in Vector4's (x, y, z, w) layout.

    Calling conventions:
        quat()              -> zero quaternion Vector4(0, 0, 0, 0)
        quat(w, x, y, z)   -> Vector4(x, y, z, w)  [PyGLM-compatible]
        quat(Vector3)       -> euler angles to quaternion [PyGLM-compatible]
        quat(Vector4)       -> copy of the Vector4
    """
    if len(args) == 0:
        return Vector4(0.0, 0.0, 0.0, 0.0)
    if len(args) == 1:
        arg = args[0]
        if isinstance(arg, Vector4):
            return Vector4(arg.x, arg.y, arg.z, arg.w)
        if isinstance(arg, Vector3):
            # Convert euler angles (x=pitch, y=yaw, z=roll) to quaternion.
            # This matches GLM's quat(vec3) constructor which uses
            # intrinsic ZYX rotation order (extrinsic XYZ).
            cx = math.cos(arg.x * 0.5)
            sx = math.sin(arg.x * 0.5)
            cy = math.cos(arg.y * 0.5)
            sy = math.sin(arg.y * 0.5)
            cz = math.cos(arg.z * 0.5)
            sz = math.sin(arg.z * 0.5)

            qw = cx * cy * cz + sx * sy * sz
            qx = sx * cy * cz - cx * sy * sz
            qy = cx * sy * cz + sx * cy * sz
            qz = cx * cy * sz - sx * sy * cz
            return Vector4(qx, qy, qz, qw)
        if isinstance(arg, (int, float)):
            # Scalar: quat(w) -> identity-like with given w
            return Vector4(0.0, 0.0, 0.0, float(arg))
        return Vector4(0.0, 0.0, 0.0, 0.0)
    if len(args) == 4:
        # quat(w, x, y, z) -> Vector4(x, y, z, w) [PyGLM convention: w first]
        w, x, y, z = args
        return Vector4(float(x), float(y), float(z), float(w))
    raise TypeError(f"quat() takes 0, 1, or 4 arguments, got {len(args)}")


# Re-export all functions
__all__ = [
    "vec2",
    "vec3",
    "vec4",
    "quat",
    "mat4",
    "translate",
    "rotate",
    "mat4_cast",
    "inverse",
    "perspective",
    "normalize",
    "cross",
    "decompose",
    "eulerAngles",
    "value_ptr",
    "unProject",
    "length",
]

# Try to import PyGLM if available (for optional performance improvements)
if not TYPE_CHECKING and importlib.util.find_spec("pyglm"):  # type: ignore[attr-defined]
    try:
        from pyglm.glm import (  # pyright: ignore[reportUnreachable]
            inverse as _pyglm_inverse,
            mat4 as _pyglm_mat4,
            quat as _pyglm_quat,
            vec3 as _pyglm_vec3,
            vec4 as _pyglm_vec4,
        )

        # Use PyGLM if available (better performance)
        vec3 = _pyglm_vec3  # type: ignore[assignment]
        vec4 = _pyglm_vec4  # type: ignore[assignment]
        quat = _pyglm_quat  # type: ignore[assignment]
        mat4 = _pyglm_mat4  # type: ignore[assignment]
        inverse = _pyglm_inverse  # type: ignore[assignment]
    except ImportError:
        from loggerplus import RobustLogger

        RobustLogger().debug("PyGLM not found, using PyKotor geometry classes")
        pass
