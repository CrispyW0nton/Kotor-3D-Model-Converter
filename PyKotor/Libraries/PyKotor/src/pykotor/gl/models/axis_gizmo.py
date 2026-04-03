"""3D axis gizmo for cursor/orientation display in the Module Designer.

Draws three colored lines (X=red, Y=green, Z=blue) forming a right-angle
gizmo at the cursor position. The gizmo is rendered as an **overlay** so it
is always visible regardless of scene geometry depth.

Rendering technique (industry standard for gizmos/handles):
1. Disable depth testing so lines are always on top.
2. Disable depth writes so the gizmo doesn't corrupt the depth buffer.
3. Use glLineWidth for visibility (thicker than the default 1px).
4. Scale axis length proportional to camera distance so the gizmo
   maintains a roughly constant apparent size on screen.
5. Restore all GL state after drawing.
"""

from __future__ import annotations

import ctypes

from typing import TYPE_CHECKING

import numpy as np

from pykotor.gl.compat import has_pyopengl, missing_constant, missing_gl_func, safe_gl_error_module

HAS_PYOPENGL = has_pyopengl()
gl_error = safe_gl_error_module()

if HAS_PYOPENGL:
    from OpenGL.GL import (  # pyright: ignore[reportMissingImports]
        GL_LINE_WIDTH,
        glGenBuffers,
        glGenVertexArrays,
        glGetFloatv,
        glLineWidth,
        glVertexAttribPointer,
    )
    from OpenGL.GL.shaders import GL_FALSE  # pyright: ignore[reportMissingImports]
    from OpenGL.raw.GL.ARB.vertex_shader import GL_FLOAT  # pyright: ignore[reportMissingImports]
    from OpenGL.raw.GL.VERSION.GL_1_0 import (  # pyright: ignore[reportMissingImports]
        GL_DEPTH_TEST,
        GL_LINES,
        glDepthMask,
        glDisable,
        glEnable,
    )
    from OpenGL.raw.GL.VERSION.GL_1_1 import glDrawArrays  # pyright: ignore[reportMissingImports]
    from OpenGL.raw.GL.VERSION.GL_1_5 import GL_ARRAY_BUFFER, GL_STATIC_DRAW, glBindBuffer, glBufferData  # pyright: ignore[reportMissingImports]
    from OpenGL.raw.GL.VERSION.GL_2_0 import glEnableVertexAttribArray  # pyright: ignore[reportMissingImports]
    from OpenGL.raw.GL.VERSION.GL_3_0 import glBindVertexArray  # pyright: ignore[reportMissingImports]
else:
    glGenBuffers = missing_gl_func("glGenBuffers")
    glGenVertexArrays = missing_gl_func("glGenVertexArrays")
    glVertexAttribPointer = missing_gl_func("glVertexAttribPointer")
    glDrawArrays = missing_gl_func("glDrawArrays")
    glBindBuffer = missing_gl_func("glBindBuffer")
    glBufferData = missing_gl_func("glBufferData")
    glEnableVertexAttribArray = missing_gl_func("glEnableVertexAttribArray")
    glBindVertexArray = missing_gl_func("glBindVertexArray")
    glLineWidth = missing_gl_func("glLineWidth")
    glGetFloatv = missing_gl_func("glGetFloatv")
    glDepthMask = missing_gl_func("glDepthMask")
    glDisable = missing_gl_func("glDisable")
    glEnable = missing_gl_func("glEnable")
    GL_FALSE = missing_constant("GL_FALSE")
    GL_LINES = missing_constant("GL_LINES")
    GL_FLOAT = missing_constant("GL_FLOAT")
    GL_ARRAY_BUFFER = missing_constant("GL_ARRAY_BUFFER")
    GL_STATIC_DRAW = missing_constant("GL_STATIC_DRAW")
    GL_DEPTH_TEST = missing_constant("GL_DEPTH_TEST")
    GL_LINE_WIDTH = missing_constant("GL_LINE_WIDTH")

from pykotor.gl.glm_compat import Vector3 as GlmVector3, translate, vec4

if TYPE_CHECKING:
    from pykotor.gl.shader import Shader

# Default gizmo line width in pixels.
GIZMO_LINE_WIDTH: float = 3.0

# Base axis length in world units. Actual length is scaled by camera distance.
_BASE_AXIS_LENGTH: float = 1.0

# Unit-length axis vertices: origin→X, origin→Y, origin→Z  (6 verts = 3 lines).
# The model matrix will handle positioning + scaling.
_AXIS_VERTICES: np.ndarray = np.array(
    [
        # X axis
        0.0,
        0.0,
        0.0,
        _BASE_AXIS_LENGTH,
        0.0,
        0.0,
        # Y axis
        0.0,
        0.0,
        0.0,
        0.0,
        _BASE_AXIS_LENGTH,
        0.0,
        # Z axis
        0.0,
        0.0,
        0.0,
        0.0,
        0.0,
        _BASE_AXIS_LENGTH,
    ],
    dtype=np.float32,
)

# Default axis colours (RGBA).
_X_COLOR = vec4(1.0, 0.0, 0.0, 1.0)  # Red
_Y_COLOR = vec4(0.0, 1.0, 0.0, 1.0)  # Green
_Z_COLOR = vec4(0.3, 0.3, 1.0, 1.0)  # Blue (slightly brighter to stand out)


class AxisGizmo:
    """Draws a 3D axis gizmo (X=red, Y=green, Z=blue) using GL_LINES.

    The gizmo is drawn as an overlay (depth test off, thick lines) so it
    is always visible. Axis length is scaled by camera distance so the
    gizmo keeps a roughly constant apparent size on screen.
    """

    __slots__ = ("_vao", "_vbo", "_vertex_count")

    def __init__(self) -> None:
        self._vertex_count: int = 6
        if HAS_PYOPENGL:
            self._vao = glGenVertexArrays(1)
            self._vbo = glGenBuffers(1)
            glBindVertexArray(self._vao)

            glBindBuffer(GL_ARRAY_BUFFER, self._vbo)
            glBufferData(GL_ARRAY_BUFFER, _AXIS_VERTICES.nbytes, _AXIS_VERTICES, GL_STATIC_DRAW)

            # Plain shader expects position at layout location 1.
            glEnableVertexAttribArray(1)
            glVertexAttribPointer(1, 3, GL_FLOAT, GL_FALSE, 12, ctypes.c_void_p(0))

            glBindBuffer(GL_ARRAY_BUFFER, 0)
            glBindVertexArray(0)
        else:
            self._vao = 0
            self._vbo = 0

    def draw(
        self,
        shader: Shader,
        position: GlmVector3,
        camera_distance: float,
        line_width: float = GIZMO_LINE_WIDTH,
    ) -> None:
        """Draw the axis gizmo at *position*, scaled to *camera_distance*.

        Args:
            shader: The plain (colour-uniform) shader, already in use with
                    view/projection uniforms set.
            position: World-space position of the gizmo origin.
            camera_distance: Distance from the camera to the focal point.
                             Used to scale the gizmo so it stays roughly
                             the same size on screen.
            line_width: Pixel width for the axis lines.
        """
        if not HAS_PYOPENGL:
            raise gl_error.NullFunctionError("PyOpenGL is unavailable.")

        # --- Build model matrix: translate to position, uniform scale by distance ---
        # Scale factor: ~5% of camera distance, clamped to a reasonable range.
        scale = max(0.25, min(camera_distance * 0.06, 8.0))
        # translate(vec3) returns a translation matrix; then apply uniform scale.
        model = translate(GlmVector3(position.x, position.y, position.z))
        # Scale the rotation/scale part of the matrix (rows 0-2, col 0-2).
        # Matrix4._data is row-major: [row][col].
        model._data[0][0] *= scale
        model._data[1][1] *= scale
        model._data[2][2] *= scale

        # --- Save GL state we're about to change ---
        old_line_width = glGetFloatv(GL_LINE_WIDTH)

        # --- Set overlay state ---
        glDisable(GL_DEPTH_TEST)  # Always on top
        glDepthMask(False)  # Don't write to depth buffer
        glLineWidth(line_width)

        shader.set_matrix4("model", model)
        glBindVertexArray(self._vao)

        # Draw X axis (red)
        shader.set_vector4("color", _X_COLOR)
        glDrawArrays(GL_LINES, 0, 2)

        # Draw Y axis (green)
        shader.set_vector4("color", _Y_COLOR)
        glDrawArrays(GL_LINES, 2, 2)

        # Draw Z axis (blue)
        shader.set_vector4("color", _Z_COLOR)
        glDrawArrays(GL_LINES, 4, 2)

        # --- Restore GL state ---
        glBindVertexArray(0)  # Unbind VAO to avoid interfering with subsequent draws
        glLineWidth(float(old_line_width) if old_line_width else 1.0)
        glDepthMask(True)
        glEnable(GL_DEPTH_TEST)
