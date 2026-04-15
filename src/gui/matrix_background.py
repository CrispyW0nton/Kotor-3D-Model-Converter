"""
Matrix Background Widget – animated MP4 video background for GhostRigger UI.

Plays a looping Matrix "digital rain" video behind the entire application
window using OpenCV for frame decoding and PIL/ImageTk for Tkinter display.

The video is drawn on a full-window Canvas positioned at the very back of the
widget stacking order via place(). All other UI elements are layered on top
using pack/grid as usual.

Performance notes
-----------------
- Frames are decoded at a reduced resolution (scaled to window size) to minimise
  CPU/memory usage.
- Frame rate is throttled to ~15 fps (66 ms interval) rather than the source
  video's native fps, since the background is a subtle ambient effect.
- A green colour-multiply tint is applied to ensure visual consistency with the
  GhostRigger cyberpunk theme regardless of the source video's colour grading.
- The widget gracefully degrades: if OpenCV is unavailable, a static dark
  background is shown instead.
"""

import os
import logging
import tkinter as tk
from typing import Optional

log = logging.getLogger(__name__)

# Attempt imports – degrade gracefully if unavailable
try:
    import cv2
    _HAS_CV2 = True
except ImportError:
    _HAS_CV2 = False

try:
    from PIL import Image, ImageTk, ImageEnhance
    _HAS_PIL = True
except ImportError:
    _HAS_PIL = False

try:
    import numpy as np
    _HAS_NP = True
except ImportError:
    _HAS_NP = False

# ── Default configuration ──────────────────────────────────────────────
_DEFAULT_VIDEO = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "assets", "matrix_bg.mp4"
)
_TARGET_FPS = 15          # Background animation fps (throttled for performance)
_FRAME_INTERVAL_MS = max(1, int(1000 / _TARGET_FPS))
_OPACITY = 0.35           # Blend opacity of the video over the dark base
_GREEN_TINT = (0, 255, 122)  # Neon-green tint (matches GhostRigger accent #00FF7A)


class MatrixBackground(tk.Canvas):
    """Full-window animated Matrix background.

    Usage
    -----
    In the main Tk window's __init__, BEFORE packing any other widgets::

        self.matrix_bg = MatrixBackground(self)
        self.matrix_bg.place(x=0, y=0, relwidth=1, relheight=1)
        # ... now pack/grid other widgets on top ...
        self.matrix_bg.start()

    Call ``stop()`` on window close to release the video capture.
    """

    def __init__(self, master: tk.Tk, video_path: Optional[str] = None,
                 bg_color: str = "#0B0F0D", opacity: float = _OPACITY, **kw):
        super().__init__(master, bg=bg_color, highlightthickness=0, **kw)
        self._bg_color = bg_color
        self._opacity = max(0.0, min(1.0, opacity))
        self._video_path = video_path or _DEFAULT_VIDEO
        self._cap: Optional[object] = None    # cv2.VideoCapture
        self._photo: Optional[object] = None  # ImageTk.PhotoImage (prevent GC)
        self._image_id: Optional[int] = None  # Canvas image item id
        self._running = False
        self._after_id: Optional[str] = None
        self._last_width = 0
        self._last_height = 0

        # Try to open the video immediately (lazy init on first frame otherwise)
        self._init_capture()

    def _init_capture(self):
        """Open the video file with OpenCV."""
        if not _HAS_CV2 or not _HAS_PIL:
            log.info("MatrixBackground: OpenCV or PIL not available – static bg only")
            return
        if not os.path.isfile(self._video_path):
            log.warning(f"MatrixBackground: video not found: {self._video_path}")
            return
        try:
            self._cap = cv2.VideoCapture(self._video_path)
            if not self._cap.isOpened():
                log.warning(f"MatrixBackground: could not open {self._video_path}")
                self._cap = None
        except Exception as e:
            log.warning(f"MatrixBackground: cv2.VideoCapture error: {e}")
            self._cap = None

    def start(self):
        """Begin the background animation loop."""
        if self._running:
            return
        self._running = True
        self._tick()

    def stop(self):
        """Stop the animation and release resources."""
        self._running = False
        if self._after_id is not None:
            try:
                self.after_cancel(self._after_id)
            except Exception:
                pass
            self._after_id = None
        if self._cap is not None:
            try:
                self._cap.release()
            except Exception:
                pass
            self._cap = None

    def set_opacity(self, opacity: float):
        """Adjust the video overlay opacity (0.0 = invisible, 1.0 = full)."""
        self._opacity = max(0.0, min(1.0, opacity))

    def _tick(self):
        """Read next video frame, process, and schedule the next tick."""
        if not self._running:
            return
        try:
            self._render_frame()
        except Exception as e:
            log.debug(f"MatrixBackground._tick error: {e}")
        # Schedule next frame
        self._after_id = self.after(_FRAME_INTERVAL_MS, self._tick)

    def _render_frame(self):
        """Decode one frame from the video and draw it on the canvas."""
        if self._cap is None or not _HAS_PIL:
            return

        # Read frame
        ret, frame = self._cap.read()
        if not ret:
            # End of video – loop back to start
            self._cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
            ret, frame = self._cap.read()
            if not ret:
                return  # truly broken

        # Get current canvas dimensions
        w = self.winfo_width()
        h = self.winfo_height()
        if w < 10 or h < 10:
            return  # widget not yet mapped

        # Resize frame to canvas dimensions (BGR format from OpenCV)
        frame = cv2.resize(frame, (w, h), interpolation=cv2.INTER_AREA)

        # Convert BGR → RGB
        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

        # Apply green tint: blend the frame towards the neon green
        # This ensures the Matrix effect matches the GhostRigger theme
        if not _HAS_NP:
            # Fallback: show unprocessed frame
            img = Image.fromarray(frame_rgb, 'RGB')
            photo = ImageTk.PhotoImage(img)
            if self._image_id is None:
                self._image_id = self.create_image(0, 0, anchor='nw', image=photo)
            else:
                self.itemconfig(self._image_id, image=photo)
            self._photo = photo
            return
        frame_f = frame_rgb.astype(np.float32)

        # Desaturate slightly first, then tint green
        gray = np.mean(frame_f, axis=2, keepdims=True)
        # Mix: 40% original colour + 60% green-tinted grayscale
        tint = np.array(_GREEN_TINT, dtype=np.float32).reshape(1, 1, 3)
        tinted = gray * (tint / 255.0)
        frame_f = frame_f * 0.4 + tinted * 0.6
        frame_f = np.clip(frame_f, 0, 255)

        # Create dark base and blend video on top with opacity
        # Dark base = (11, 15, 13) matches C['bg'] = "#0B0F0D"
        base = np.full_like(frame_f, [11.0, 15.0, 13.0])
        blended = base * (1.0 - self._opacity) + frame_f * self._opacity
        blended = np.clip(blended, 0, 255).astype(np.uint8)

        # Convert to PIL Image → PhotoImage
        img = Image.fromarray(blended, 'RGB')
        photo = ImageTk.PhotoImage(img)

        # Draw on canvas (reuse item if same size)
        if self._image_id is None or w != self._last_width or h != self._last_height:
            self.delete("all")
            self._image_id = self.create_image(0, 0, anchor='nw', image=photo)
            self._last_width = w
            self._last_height = h
        else:
            self.itemconfig(self._image_id, image=photo)

        # Keep reference to prevent garbage collection
        self._photo = photo

    def destroy(self):
        """Clean up on widget destruction."""
        self.stop()
        super().destroy()
