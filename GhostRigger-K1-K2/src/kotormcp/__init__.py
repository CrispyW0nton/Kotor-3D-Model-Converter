"""
GhostRigger KotorMCP integration.

Provides an MCP (Model Context Protocol) server embedded in GhostRigger that exposes
KotOR installation resources and GhostRigger-specific tools (render_model, open_mdl, etc.)
to AI agents like Claude.

Architecture
------------
* src/kotormcp/server.py        — MCP server (stdio / HTTP-SSE / streamable-HTTP)
* src/kotormcp/state.py         — installation cache + path resolution
* src/kotormcp/mcp_resources.py — kotor:// URI scheme
* src/kotormcp/tools/           — per-domain tool modules
* src/kotormcp/schemas/         — Pydantic v2 input models
* src/kotormcp/utils/           — shared helpers (formatting, etc.)

Quick start (stdio mode for Claude Desktop):
    python -m kotormcp

Quick start (HTTP mode for programmatic use):
    python -m kotormcp --mode http --port 8765
"""

from __future__ import annotations

__version__ = "1.0.0"
__all__ = ["__version__"]
