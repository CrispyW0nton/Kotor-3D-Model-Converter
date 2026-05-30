"""Arc-ball camera implementation for the viewport frame renderer."""

from __future__ import annotations

import math

from src.gui.rendering.frame_core.math_helpers import _clamp, _cross, _dot, _normalize, _sub

# ─────────────────────────────────────────────────────────────────────
#  Arc-ball Camera (Maya style)
# ─────────────────────────────────────────────────────────────────────

class ArcBallCamera:
    """
    Orbital camera.
      • LMB drag   → orbit  (azimuth / elevation)
      • MMB / RMB  → pan    (shift target)
      • Scroll     → zoom
    """
    DEFAULT_AZIMUTH = 90.0
    DEFAULT_ELEVATION = 20.0

    def __init__(self):
        # KotOR actors face +Y, so the canonical front view places the eye on
        # +Y and looks back toward the model centre.
        self.azimuth   = self.DEFAULT_AZIMUTH
        self.elevation = self.DEFAULT_ELEVATION
        self.distance  = 5.0
        self.target    = [0.0, 1.0, 0.0]
        self.fov       = 45.0
        self._near     = 0.01
        self._far      = 1000.0

    # ── eye position ──────────────────────────────────────────────────

    def eye(self):
        """Camera eye position. KotOR is Z-up, so elevation rotates in XZ plane."""
        az = math.radians(self.azimuth)
        el = math.radians(self.elevation)
        ce = math.cos(el)
        x  = self.distance * ce * math.cos(az)
        y  = self.distance * ce * math.sin(az)
        z  = self.distance * math.sin(el)
        return (self.target[0]+x, self.target[1]+y, self.target[2]+z)

    # ── controls ──────────────────────────────────────────────────────

    def orbit(self, daz: float, del_: float):
        self.azimuth   = (self.azimuth + daz) % 360.0
        self.elevation = _clamp(self.elevation + del_, -85.0, 85.0)

    def zoom(self, steps: float):
        self.distance = max(0.05, self.distance * (0.9 ** steps))
        self._sync_close_clip_plane()

    def _sync_close_clip_plane(self):
        """Keep close zooms from slicing animated/inspected geometry."""
        close_near = max(0.001, float(self.distance) * 0.02)
        self._near = max(0.001, min(float(self._near), close_near))
        self._far = max(float(self._far), float(self.distance) * 4.0 + 1.0)

    def pan(self, dx_px: float, dy_px: float, viewport_h: int):
        right, up, fwd, eye = self._view_matrix()
        scale = self.distance / max(viewport_h, 1) * 1.8
        self.target[0] -= right[0] * dx_px * scale
        self.target[1] -= right[1] * dx_px * scale
        self.target[2] -= right[2] * dx_px * scale
        self.target[0] += up[0] * dy_px * scale
        self.target[1] += up[1] * dy_px * scale
        self.target[2] += up[2] * dy_px * scale

    def frame_bounds(self, bb_min, bb_max, reset_view: bool = False):
        """Fit camera to bounding box using screen-space projection (Z-up world).

        Instead of using the raw 3-D diagonal (which over-distances wide/flat
        models like quadrupeds or banthas), we iterate over the 8 BB corners,
        project them onto the camera's right/up plane, and derive the minimum
        distance required so that all projected corners fit inside the FOV.

        ``reset_view`` also restores the canonical front camera.  Plain
        frame-all preserves the user's current orbit and only adjusts target
        and distance.
        """
        cx = (bb_min[0] + bb_max[0]) * 0.5
        cy = (bb_min[1] + bb_max[1]) * 0.5
        cz = (bb_min[2] + bb_max[2]) * 0.5
        self.target    = [cx, cy, cz]
        if reset_view:
            self.azimuth = self.DEFAULT_AZIMUTH
            self.elevation = self.DEFAULT_ELEVATION

        # Compute a safe initial distance (3-D diagonal) just to get camera vectors
        dx = bb_max[0] - bb_min[0]
        dy = bb_max[1] - bb_min[1]
        dz = bb_max[2] - bb_min[2]
        diag = math.sqrt(dx*dx + dy*dy + dz*dz)
        self.distance = max(0.5, diag * 1.1)

        # Compute camera right/up vectors at current orientation
        az = math.radians(self.azimuth)
        el = math.radians(self.elevation)
        fwd_v  = (-math.cos(el)*math.cos(az),
                  -math.cos(el)*math.sin(az),
                  -math.sin(el))
        world_up = (0.0, 0.0, 1.0)
        right_v = _normalize(_cross(fwd_v, world_up))
        if _dot(right_v, right_v) < 1e-6:
            right_v = _normalize(_cross(fwd_v, (0.0, 1.0, 0.0)))
        up_v = _normalize(_cross(right_v, fwd_v))

        # 8 corners of the bounding box relative to centre
        corners = [
            (bb_min[0]-cx, bb_min[1]-cy, bb_min[2]-cz),
            (bb_max[0]-cx, bb_min[1]-cy, bb_min[2]-cz),
            (bb_min[0]-cx, bb_max[1]-cy, bb_min[2]-cz),
            (bb_max[0]-cx, bb_max[1]-cy, bb_min[2]-cz),
            (bb_min[0]-cx, bb_min[1]-cy, bb_max[2]-cz),
            (bb_max[0]-cx, bb_min[1]-cy, bb_max[2]-cz),
            (bb_min[0]-cx, bb_max[1]-cy, bb_max[2]-cz),
            (bb_max[0]-cx, bb_max[1]-cy, bb_max[2]-cz),
        ]

        # Project each corner onto right/up plane; find max screen extent
        max_right = max_up = max_depth = 0.0
        for c in corners:
            pr = abs(_dot(c, right_v))
            pu = abs(_dot(c, up_v))
            pd = abs(_dot(c, fwd_v))
            if pr > max_right: max_right = pr
            if pu > max_up:    max_up    = pu
            if pd > max_depth:  max_depth = pd

        # Determine required distance so the extent fits inside the FOV
        # At distance d: half_screen_world = d * tan(fov/2)
        # We need half_screen_world >= max(max_right, max_up) * 1.15 (5% margin)
        half_fov_tan = math.tan(math.radians(self.fov) * 0.5)
        screen_extent = max(max_right, max_up, 0.01)
        fitted_dist   = (screen_extent * 1.18) / half_fov_tan

        # Also keep enough depth margin to avoid near-plane clipping.
        min_dist = max(0.3, max_depth * 1.25)

        self.distance = max(fitted_dist, min_dist)

        # Keep GPU projection clipping in step with the framed asset.  The
        # software path only rejects against the near plane, but WGPU/D3D also
        # uses the far plane for depth and frustum culling; large modules can
        # easily outgrow the default 1000-unit clip range.
        nearest_depth = max(0.001, self.distance - max_depth)
        farthest_depth = max(1.0, self.distance + max_depth)
        diag_extent = max(0.01, diag)
        self._near = max(0.001, min(nearest_depth * 0.25, diag_extent * 0.001, 0.05))
        self._far = max(1000.0, farthest_depth * 2.0)
        self._sync_close_clip_plane()

    # ── projection helpers ────────────────────────────────────────────

    def _view_matrix(self):
        """Returns (right, up, fwd) unit vectors + eye position."""
        eye = self.eye()
        fwd = _normalize(_sub(self.target, eye))
        world_up = (0.0, 0.0, 1.0)
        right = _normalize(_cross(fwd, world_up))
        if _dot(right, right) < 1e-6:
            world_up = (0.0, 1.0, 0.0)
            right = _normalize(_cross(fwd, world_up))
        up = _cross(right, fwd)
        return right, up, fwd, eye

    def project(self, x, y, z, W, H):
        """Project world point to screen pixel (sx, sy, depth). Returns None if behind camera."""
        right, up, fwd, eye = self._view_matrix()
        dx, dy, dz = x - eye[0], y - eye[1], z - eye[2]
        cx =  _dot((dx,dy,dz), right)
        cy =  _dot((dx,dy,dz), up)
        cz =  _dot((dx,dy,dz), fwd)
        if cz < self._near:
            return None
        f   = 1.0 / math.tan(math.radians(self.fov) * 0.5)
        sx  = int(W * 0.5 + (cx / cz) * f * H * 0.5)
        sy  = int(H * 0.5 - (cy / cz) * f * H * 0.5)
        return sx, sy, cz



__all__ = tuple(name for name in globals() if not name.startswith('__'))
