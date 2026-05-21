"""Safe-frame, guide, and letterbox overlay drawing."""

from __future__ import annotations


class CameraOverlays:
    def draw(self, draw, camera, width: int, height: int, *, include_guides: bool = True) -> None:
        frame = self.active_frame_rect(camera, width, height)
        if bool(getattr(camera, "show_letterbox", False)):
            self.draw_letterbox(draw, frame, width, height)
        if bool(getattr(camera, "show_safe_frame", False)):
            self.draw_safe_frame(draw, frame)
        if include_guides:
            self.draw_guides(draw, frame)

    def active_frame_rect(self, camera, width: int, height: int) -> tuple[int, int, int, int]:
        render_aspect = max(0.05, float(getattr(camera, "aspect_ratio_width", 16)) / max(1.0, float(getattr(camera, "aspect_ratio_height", 9))))
        target_aspect = render_aspect
        if bool(getattr(camera, "show_letterbox", False)):
            target_aspect = max(0.1, float(getattr(camera, "letterbox_ratio", render_aspect)))
        viewport_aspect = max(0.05, float(width) / max(1.0, float(height)))
        if viewport_aspect > target_aspect:
            frame_h = int(height)
            frame_w = int(round(frame_h * target_aspect))
        else:
            frame_w = int(width)
            frame_h = int(round(frame_w / target_aspect))
        left = max(0, (int(width) - frame_w) // 2)
        top = max(0, (int(height) - frame_h) // 2)
        return (left, top, left + frame_w, top + frame_h)

    def draw_letterbox(
        self,
        draw,
        frame: tuple[int, int, int, int],
        width: int,
        height: int,
        *,
        opaque: bool = False,
    ) -> None:
        left, top, right, bottom = frame
        fill = (0, 0, 0, 255 if opaque else 220)
        if top > 0:
            draw.rectangle([0, 0, width, top], fill=fill)
        if bottom < height:
            draw.rectangle([0, bottom, width, height], fill=fill)
        if left > 0:
            draw.rectangle([0, top, left, bottom], fill=fill)
        if right < width:
            draw.rectangle([right, top, width, bottom], fill=fill)

    def draw_safe_frame(self, draw, frame: tuple[int, int, int, int]) -> None:
        left, top, right, bottom = frame
        draw.rectangle([left, top, right, bottom], outline=(235, 235, 235, 170), width=1)
        w = right - left
        h = bottom - top
        action = (left + int(w * 0.05), top + int(h * 0.05), right - int(w * 0.05), bottom - int(h * 0.05))
        title = (left + int(w * 0.10), top + int(h * 0.10), right - int(w * 0.10), bottom - int(h * 0.10))
        draw.rectangle(action, outline=(235, 235, 235, 115), width=1)
        draw.rectangle(title, outline=(235, 235, 235, 85), width=1)

    def draw_guides(self, draw, frame: tuple[int, int, int, int]) -> None:
        left, top, right, bottom = frame
        w = right - left
        h = bottom - top
        guide = (235, 235, 235, 65)
        for x in (left + w // 3, left + (2 * w) // 3):
            draw.line([x, top, x, bottom], fill=guide, width=1)
        for y in (top + h // 3, top + (2 * h) // 3):
            draw.line([left, y, right, y], fill=guide, width=1)
        cx = left + w // 2
        cy = top + h // 2
        draw.line([cx - 8, cy, cx + 8, cy], fill=(235, 235, 235, 90), width=1)
        draw.line([cx, cy - 8, cx, cy + 8], fill=(235, 235, 235, 90), width=1)
