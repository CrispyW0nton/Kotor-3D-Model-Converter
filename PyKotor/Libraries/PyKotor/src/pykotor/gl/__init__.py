"""PyKotorGL - OpenGL rendering module for PyKotor.

Automatically uses PyGLM when available (CPython),
or falls back to NumPy-based glm_compat (PyPy).
"""

from __future__ import annotations

# Try to import PyGLM, fall back to our compatibility layer
from pykotor.gl.glm_compat import (  # type: ignore[assignment]
    cross,
    decompose,
    eulerAngles,
    inverse,
    mat4,
    mat4_cast,
    normalize,
    perspective,
    quat,
    rotate,
    translate,
    unProject,
    value_ptr,
    vec3,
    vec4,
)

GLM_AVAILABLE = False
try:
    import pyglm.glm
    from pyglm.glm import mat4, quat, vec3, vec4  # type: ignore[import-not-found]

    glm = pyglm.glm

    GLM_AVAILABLE = True
except ImportError:
    # Create a glm module namespace for compatibility
    class _GLMNamespace:
        cross = staticmethod(cross)
        decompose = staticmethod(decompose)
        eulerAngles = staticmethod(eulerAngles)
        inverse = staticmethod(inverse)
        mat4_cast = staticmethod(mat4_cast)
        normalize = staticmethod(normalize)
        perspective = staticmethod(perspective)
        rotate = staticmethod(rotate)
        translate = staticmethod(translate)
        unProject = staticmethod(unProject)
        value_ptr = staticmethod(value_ptr)
        quat = staticmethod(quat)  # quat is a function, needs staticmethod
        vec3 = vec3
        vec4 = vec4
        mat4 = mat4

    glm = _GLMNamespace()  # type: ignore[assignment]
    vec3 = glm.vec3
    vec4 = glm.vec4
    mat4 = glm.mat4

__all__ = [
    "GLM_AVAILABLE",
    "glm",
    "mat4",
    "quat",
    "cross",
    "decompose",
    "eulerAngles",
    "inverse",
    "mat4_cast",
    "normalize",
    "perspective",
    "rotate",
    "translate",
    "unProject",
    "value_ptr",
    "vec3",
    "value_ptr",
    "vec4",
    "unProject",
]
