"""Renderer-neutral GPU diagnostic environment helpers."""

from __future__ import annotations

import os


_GL_STATE_TRACE_ENV = "GHOSTRIGGER_GL_STATE_TRACE"
_GL_DEBUG_ERRORS_ENV = "GHOSTRIGGER_GL_DEBUG_ERRORS"
_GL_STATE_TRACE_TRUE = {"1", "true", "yes", "on"}
_GL_STATE_TRACE_FALSE = {"0", "false", "no", "off", ""}
_GL_BACKEND_ENV = "GHOSTRIGGER_GL_BACKEND"
_DEBUG_VIZ_ENV = "GHOSTRIGGER_DEBUG_VIZ"
_LM_DATA_DUMP_ENV = "GHOSTRIGGER_LM_DATA_DUMP"
_LM_COMPOSITE_MODE_ENV = "GHOSTRIGGER_LM_COMPOSITE_MODE"
_SKIN_DUMP_ENV = "GHOSTRIGGER_SKIN_DUMP"


def _path_from_env(name: str) -> str:
    return os.environ.get(name, "").strip()


def _int_env_clamped(name: str, *, minimum: int, maximum: int, default: int = 0) -> int:
    try:
        value = int(str(os.environ.get(name, "")).strip())
    except Exception:
        return default
    return max(minimum, min(maximum, value))


def _gl_state_trace_path() -> str:
    return _path_from_env(_GL_STATE_TRACE_ENV)


def _lm_data_dump_path() -> str:
    return _path_from_env(_LM_DATA_DUMP_ENV)


def _skin_dump_path() -> str:
    return _path_from_env(_SKIN_DUMP_ENV)


def _debug_visualize_mode() -> int:
    return _int_env_clamped(_DEBUG_VIZ_ENV, minimum=0, maximum=4)


def _lm_composite_mode() -> int:
    return _int_env_clamped(_LM_COMPOSITE_MODE_ENV, minimum=0, maximum=3)
