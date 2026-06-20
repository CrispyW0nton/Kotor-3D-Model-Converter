"""Response formatting: JSON content, truncation, pagination helpers."""

from __future__ import annotations

import json
from typing import Any, Dict


# Recommended max response size for tool output; truncate with continuation hint when exceeded
MAX_RESPONSE_CHARS = 25_000
CONTINUATION_HINT = (
    "Response exceeded character limit; use offset/limit or filters to request a smaller result."
)


def json_content(payload: Any, max_chars: int = MAX_RESPONSE_CHARS) -> Dict[str, Any]:
    """Build a JSON-serializable dict from payload.

    Returns {"type": "text", "text": "<json>"} — the canonical tool-result
    format used throughout GhostRigger KotorMCP.  The MCP server (server.py)
    reads raw["text"] from this dict and wraps it in TextContent.

    If serialized length exceeds max_chars, wraps payload in a truncation
    envelope with continuation_hint.
    """
    text = json.dumps(payload, ensure_ascii=False, indent=2)
    if len(text) <= max_chars:
        return {"type": "text", "text": text}

    preview_limit = max(0, max_chars - 500)
    wrapper: Dict[str, Any] = {
        "truncated": True,
        "continuation_hint": CONTINUATION_HINT,
        "truncated_preview": text[:preview_limit],
    }
    out = json.dumps(wrapper, ensure_ascii=False, indent=2)
    while len(out) > max_chars and preview_limit > 0:
        preview_limit = max(0, preview_limit - max(100, (len(out) - max_chars)))
        wrapper["truncated_preview"] = text[:preview_limit]
        out = json.dumps(wrapper, ensure_ascii=False, indent=2)
    return {"type": "text", "text": out}


def make_tool_result(payload: Any, max_chars: int = MAX_RESPONSE_CHARS):
    """Build an mcp.types.CallToolResult if mcp is available, else return a plain dict."""
    content_dict = json_content(payload, max_chars)
    try:
        from mcp import types  # type: ignore[import]  # noqa: PLC0415
        return types.CallToolResult(
            content=[types.TextContent(type="text", text=content_dict["text"])]
        )
    except ImportError:
        return content_dict
