"""Native OS light/dark detection."""

from __future__ import annotations

import logging

log = logging.getLogger(__name__)


class OSThemeDetector:
    """Small wrapper around darkdetect so import failures never reach the UI."""

    def current_mode(self) -> str:
        try:
            import darkdetect

            if bool(darkdetect.isDark()):
                return "dark"
            if bool(darkdetect.isLight()):
                return "light"
        except Exception as exc:
            log.debug("darkdetect failed: %s", exc)
        return "dark"

    def is_dark(self) -> bool:
        return self.current_mode() == "dark"
