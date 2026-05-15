# ─────────────────────────────────────────────────────────────────────────────
#  ⚠  FROZEN — LEGACY TKINTER MODULE  ⚠
# ─────────────────────────────────────────────────────────────────────────────
#  This file is part of the pre-Qt GhostRigger UI and is kept ONLY as a
#  read-only reference until milestone M3 (T302) deletes it.
#
#  Do NOT add new features here.  Do NOT touch business logic here.
#  All active UI work happens under qt_*.py in this package.
#
#  Tracking: knowledge_base/roadmap/02_roadmap_2026_05.md  (M0/T004, M3/T302)
# ─────────────────────────────────────────────────────────────────────────────
"""
Matrix Background Engine – animated MP4 video background for GhostRigger UI.

Architecture
------------
- **MatrixEngine** (singleton): Decodes video frames in a background-friendly
  loop, produces a full-window-sized PIL Image each tick, and notifies all
  registered subscriber widgets to repaint.
- **MatrixPanel**: A tk.Canvas that acts as a drop-in replacement for tk.Frame.
  Each tick it receives the full-window frame, crops its own screen region,
  and draws the cropped slice as its canvas background image.
  Child widgets are placed **directly on the Canvas** via create_window(),
  so the Matrix rain is visible in every gap between child widgets.

This lets the Matrix digital rain appear to flow seamlessly across the header,
toolbar, side panels, and status bar — as if they were transparent windows
looking onto a single animated backdrop.

Performance notes
-----------------
- Single video decode shared across all panels (not one decode per panel).
- Frames decoded at full window size once, then each panel crops its region.
- Throttled to ~12 fps for subtle ambient animation without CPU overhead.
- Graceful degradation: if OpenCV is unavailable, panels render as plain dark frames.
"""

import os
import logging
import sys
import tkinter as tk
from typing import Optional, List, Callable

log = logging.getLogger(__name__)


def _env_enabled(name: str, default: bool = False) -> bool:
    raw = os.environ.get(name, "").strip().lower()
    if not raw:
        return default
    return raw in ("1", "true", "yes", "on")


def _matrix_enabled_by_default() -> bool:
    """Avoid OpenCV video decoding in frozen Windows builds unless requested."""
    if _env_enabled("GHOSTRIGGER_DISABLE_MATRIX_BG"):
        return False
    if getattr(sys, "frozen", False):
        return _env_enabled("GHOSTRIGGER_MATRIX_BG")
    return _env_enabled("GHOSTRIGGER_MATRIX_BG", default=True)


_MATRIX_ENABLED_DEFAULT = _matrix_enabled_by_default()

# ── Optional dependency imports (graceful degradation) ────────────────
try:
    if _MATRIX_ENABLED_DEFAULT:
        import cv2
        _HAS_CV2 = True
    else:
        cv2 = None
        _HAS_CV2 = False
except ImportError:
    cv2 = None
    _HAS_CV2 = False

try:
    if _MATRIX_ENABLED_DEFAULT:
        from PIL import Image, ImageTk
        _HAS_PIL = True
    else:
        Image = ImageTk = None
        _HAS_PIL = False
except ImportError:
    Image = ImageTk = None
    _HAS_PIL = False

try:
    if _MATRIX_ENABLED_DEFAULT:
        import numpy as np
        _HAS_NP = True
    else:
        np = None
        _HAS_NP = False
except ImportError:
    np = None
    _HAS_NP = False

# ── Configuration ─────────────────────────────────────────────────────
_DEFAULT_VIDEO = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "assets", "matrix_bg.mp4"
)
_TARGET_FPS = 12
_FRAME_INTERVAL_MS = max(1, int(1000 / _TARGET_FPS))
_OPACITY = 0.50          # higher default so the rain is clearly visible
_GREEN_TINT = (0, 255, 122)
_BASE_RGB = (11, 15, 13)  # C['bg'] = "#0B0F0D"

# ======================================================================
#  MatrixEngine – singleton frame decoder
# ======================================================================

class MatrixEngine:
    """Singleton video frame provider.

    Decodes one frame per tick and broadcasts a full-window PIL Image
    to all registered MatrixPanels.

    Usage::

        engine = MatrixEngine(root_window)
        engine.start()
        # ... create MatrixPanel(parent, engine=engine) ...
        engine.stop()    # on app close
    """

    def __init__(self, root: tk.Tk, video_path: Optional[str] = None,
                 opacity: float = _OPACITY):
        self._root = root
        self._video_path = video_path or _DEFAULT_VIDEO
        self._opacity = max(0.0, min(1.0, opacity))
        self._cap = None
        self._running = False
        self._after_id = None
        self._panels: List['MatrixPanel'] = []
        self._callbacks: List[Callable] = []
        self._current_frame: Optional['Image.Image'] = None
        self._last_w = 0
        self._last_h = 0
        self._enabled = _matrix_enabled_by_default()
        if not self._enabled:
            log.info("MatrixEngine: disabled")
            return
        self._init_capture()

    # ── Video capture init ────────────────────────────────────────────
    def _init_capture(self):
        if not _HAS_CV2 or not _HAS_PIL or not _HAS_NP:
            log.info("MatrixEngine: missing deps (cv2/PIL/numpy) – static bg")
            return
        if not os.path.isfile(self._video_path):
            log.warning("MatrixEngine: video not found: %s", self._video_path)
            return
        try:
            self._cap = cv2.VideoCapture(self._video_path)
            if not self._cap.isOpened():
                log.warning("MatrixEngine: cannot open %s", self._video_path)
                self._cap = None
        except Exception as exc:
            log.warning("MatrixEngine: error: %s", exc)
            self._cap = None

    @property
    def available(self) -> bool:
        """True if the video is loaded and ready to play."""
        return self._cap is not None

    # ── Panel / callback registration ─────────────────────────────────
    def register(self, panel: 'MatrixPanel'):
        if panel not in self._panels:
            self._panels.append(panel)

    def unregister(self, panel: 'MatrixPanel'):
        try:
            self._panels.remove(panel)
        except ValueError:
            pass

    def add_callback(self, cb: Callable):
        """Register an arbitrary callback(PIL.Image) called each tick."""
        if cb not in self._callbacks:
            self._callbacks.append(cb)

    def remove_callback(self, cb: Callable):
        try:
            self._callbacks.remove(cb)
        except ValueError:
            pass

    # ── Lifecycle ─────────────────────────────────────────────────────
    def start(self):
        if not self._enabled:
            return
        if self._running:
            return
        self._running = True
        log.info("MatrixEngine: started (video=%s, opacity=%.2f)",
                 os.path.basename(self._video_path), self._opacity)
        self._tick()

    def stop(self):
        self._running = False
        if self._after_id is not None:
            try:
                self._root.after_cancel(self._after_id)
            except Exception:
                pass
            self._after_id = None
        if self._cap is not None:
            try:
                self._cap.release()
            except Exception:
                pass
            self._cap = None

    # ── Frame loop ────────────────────────────────────────────────────
    def _tick(self):
        if not self._running:
            return
        try:
            suspend_until = float(getattr(self._root, '_suspend_viewport_render_until', 0.0) or 0.0)
        except Exception:
            suspend_until = 0.0
        if suspend_until > 0:
            self._after_id = self._root.after(500, self._tick)
            return
        try:
            self._decode_frame()
            self._broadcast()
        except Exception as exc:
            log.debug("MatrixEngine._tick: %s", exc)
        self._after_id = self._root.after(_FRAME_INTERVAL_MS, self._tick)

    def _decode_frame(self):
        """Decode one video frame, tint green, blend, store as PIL Image."""
        if self._cap is None:
            return

        ret, frame = self._cap.read()
        if not ret:
            self._cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
            ret, frame = self._cap.read()
            if not ret:
                return

        w = self._root.winfo_width()
        h = self._root.winfo_height()
        if w < 10 or h < 10:
            return

        frame = cv2.resize(frame, (w, h), interpolation=cv2.INTER_AREA)
        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

        # Green tint + opacity blend over dark base
        frame_f = frame_rgb.astype(np.float32)
        gray = np.mean(frame_f, axis=2, keepdims=True)
        tint = np.array(_GREEN_TINT, dtype=np.float32).reshape(1, 1, 3)
        tinted = gray * (tint / 255.0)
        frame_f = frame_f * 0.35 + tinted * 0.65   # strong green tint
        frame_f = np.clip(frame_f, 0, 255)

        base = np.full_like(frame_f, list(_BASE_RGB), dtype=np.float32)
        blended = base * (1.0 - self._opacity) + frame_f * self._opacity
        blended = np.clip(blended, 0, 255).astype(np.uint8)

        self._current_frame = Image.fromarray(blended, 'RGB')
        self._last_w = w
        self._last_h = h

    def _broadcast(self):
        """Send current frame to all registered panels and callbacks."""
        if self._current_frame is None:
            return
        for panel in self._panels:
            try:
                panel._update_background(self._current_frame)
            except Exception:
                pass
        for cb in self._callbacks:
            try:
                cb(self._current_frame)
            except Exception:
                pass


# ======================================================================
#  MatrixPanel – Canvas with animated Matrix video background
# ======================================================================

class MatrixPanel(tk.Canvas):
    """Drop-in replacement for tk.Frame that shows animated Matrix rain.

    The panel registers itself with a MatrixEngine.  Each tick the engine
    provides a full-window PIL Image; MatrixPanel crops the region
    corresponding to its own screen position and draws it as a background.

    **Children are placed directly on the Canvas via create_window()**,
    so the Matrix rain is visible in every gap between child widgets
    (between buttons, around labels, in padding areas).

    For convenience, ``panel.inner`` is still available as a plain Frame
    for cases where you need standard pack/grid children — but its bg is
    set to a near-transparent dark colour so the matrix shows in the gaps
    around it.  For maximum visibility, place children directly::

        engine = MatrixEngine(root)
        panel = MatrixPanel(parent, engine=engine, height=48)
        panel.pack(fill='x')
        # Direct canvas windows — matrix visible in gaps:
        lbl = tk.Label(panel, text="Hello", bg='#0B0F0D', fg='#00FF7A')
        panel.create_window(10, 10, anchor='nw', window=lbl)
    """

    _BG_COLOR = "#0B0F0D"

    def __init__(self, master, engine: Optional[MatrixEngine] = None,
                 bg_color: Optional[str] = None, no_inner: bool = False,
                 **kw):
        height = kw.pop('height', None)
        _bg = bg_color or self._BG_COLOR
        super().__init__(master, bg=_bg, highlightthickness=0, **kw)
        if height is not None:
            self.configure(height=height)

        self._engine = engine
        self._bg_color = _bg
        self._photo = None      # prevent GC
        self._img_id = None     # canvas image item
        self._last_cw = 0
        self._last_ch = 0
        self._no_inner = no_inner

        if not no_inner:
            # Inner frame for pack/grid children — background matches dark base.
            self.inner = tk.Frame(self, bg=_bg)
            self._win_id = self.create_window(0, 0, anchor='nw',
                                              window=self.inner)
        else:
            # No inner frame: children placed via create_window() directly.
            # The Matrix rain is visible everywhere between child widgets.
            self.inner = None
            self._win_id = None

        self.bind('<Configure>', self._on_configure)

        if engine is not None:
            engine.register(self)

    def _on_configure(self, event=None):
        w = self.winfo_width()
        h = self.winfo_height()
        if w > 0 and h > 0 and self._win_id is not None:
            self.itemconfig(self._win_id, width=w, height=h)

    def pack_propagate(self, flag=True):
        if self.inner is not None:
            self.inner.pack_propagate(flag)

    # ── Background painting ───────────────────────────────────────────
    def _update_background(self, full_frame: 'Image.Image'):
        """Crop the full-window frame to this panel's region and draw it."""
        if not _HAS_PIL:
            return

        cw = self.winfo_width()
        ch = self.winfo_height()
        if cw < 2 or ch < 2:
            return

        try:
            rx = self.winfo_rootx() - self._get_root().winfo_rootx()
            ry = self.winfo_rooty() - self._get_root().winfo_rooty()
        except Exception:
            rx, ry = 0, 0

        fw, fh = full_frame.size

        x1 = max(0, min(rx, fw - 1))
        y1 = max(0, min(ry, fh - 1))
        x2 = max(x1 + 1, min(rx + cw, fw))
        y2 = max(y1 + 1, min(ry + ch, fh))

        cropped = full_frame.crop((x1, y1, x2, y2))
        if cropped.size != (cw, ch):
            cropped = cropped.resize((cw, ch), Image.NEAREST)

        photo = ImageTk.PhotoImage(cropped)

        if self._img_id is None or cw != self._last_cw or ch != self._last_ch:
            if self._img_id is not None:
                self.delete(self._img_id)
            self._img_id = self.create_image(0, 0, anchor='nw', image=photo)
            # Background image behind the inner frame window
            self.tag_lower(self._img_id)
            self._last_cw = cw
            self._last_ch = ch
        else:
            self.itemconfig(self._img_id, image=photo)

        self._photo = photo

    def _get_root(self) -> tk.Tk:
        w = self
        while w.master is not None:
            w = w.master
        return w

    def destroy(self):
        if self._engine is not None:
            self._engine.unregister(self)
        super().destroy()


# ======================================================================
#  MatrixLabel – a Label that paints its own background from the engine
# ======================================================================

class MatrixLabel(tk.Canvas):
    """A label widget whose background is the animated Matrix rain.

    Uses a Canvas that:
    1. Draws the cropped matrix video frame as its background image
    2. Draws text on top with canvas create_text

    This makes the matrix rain directly visible behind the text, rather
    than being hidden by an opaque Label background.
    """

    def __init__(self, master, engine: Optional[MatrixEngine] = None,
                 text: str = "", font=None, fg: str = "#00FF7A",
                 bg_color: str = "#0B0F0D", anchor: str = 'w',
                 padx: int = 4, pady: int = 2, **kw):
        _font = font or ("Consolas", 9)
        # Compute approximate size from text
        super().__init__(master, bg=bg_color, highlightthickness=0, **kw)
        self._engine = engine
        self._bg_color = bg_color
        self._text = text
        self._font = _font
        self._fg = fg
        self._anchor = anchor
        self._padx = padx
        self._pady = pady

        self._photo = None
        self._img_id = None
        self._text_id = self.create_text(
            padx, pady, text=text, font=_font, fill=fg,
            anchor='nw')
        self._last_cw = 0
        self._last_ch = 0

        self.bind('<Configure>', self._on_configure)
        if engine is not None:
            engine.register(self)

    def _on_configure(self, event=None):
        cw = self.winfo_width()
        ch = self.winfo_height()
        if cw > 0 and ch > 0:
            # Reposition text based on anchor
            if self._anchor == 'w':
                self.coords(self._text_id, self._padx, ch // 2)
                self.itemconfig(self._text_id, anchor='w')
            elif self._anchor == 'e':
                self.coords(self._text_id, cw - self._padx, ch // 2)
                self.itemconfig(self._text_id, anchor='e')
            else:
                self.coords(self._text_id, cw // 2, ch // 2)
                self.itemconfig(self._text_id, anchor='center')

    def set_text(self, text: str):
        self._text = text
        self.itemconfig(self._text_id, text=text)

    def set_fg(self, fg: str):
        self._fg = fg
        self.itemconfig(self._text_id, fill=fg)

    def _update_background(self, full_frame: 'Image.Image'):
        if not _HAS_PIL:
            return
        cw = self.winfo_width()
        ch = self.winfo_height()
        if cw < 2 or ch < 2:
            return
        try:
            rx = self.winfo_rootx() - self._get_root().winfo_rootx()
            ry = self.winfo_rooty() - self._get_root().winfo_rooty()
        except Exception:
            rx, ry = 0, 0

        fw, fh = full_frame.size
        x1 = max(0, min(rx, fw - 1))
        y1 = max(0, min(ry, fh - 1))
        x2 = max(x1 + 1, min(rx + cw, fw))
        y2 = max(y1 + 1, min(ry + ch, fh))

        cropped = full_frame.crop((x1, y1, x2, y2))
        if cropped.size != (cw, ch):
            cropped = cropped.resize((cw, ch), Image.NEAREST)

        photo = ImageTk.PhotoImage(cropped)
        if self._img_id is None or cw != self._last_cw or ch != self._last_ch:
            if self._img_id is not None:
                self.delete(self._img_id)
            self._img_id = self.create_image(0, 0, anchor='nw', image=photo)
            self.tag_lower(self._img_id)
            self._last_cw = cw
            self._last_ch = ch
        else:
            self.itemconfig(self._img_id, image=photo)
        self._photo = photo

    def _get_root(self) -> tk.Tk:
        w = self
        while w.master is not None:
            w = w.master
        return w

    def destroy(self):
        if self._engine is not None:
            self._engine.unregister(self)
        super().destroy()


# ======================================================================
#  Legacy compat aliases
# ======================================================================

class MatrixBackground(MatrixPanel):
    """Legacy alias for MatrixPanel (backward compatibility)."""
    pass
