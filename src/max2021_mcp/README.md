# 3ds Max 2021 MCP Server

This package contains a small MCP server for 3ds Max research workflows.

## Purpose

- Help inspect 3ds Max scene/runtime state from a stable tool interface.
- Use as a scratch surface for studying how 3ds Max modeling tools behave before
  porting capabilities into GhostRigger.

## Tools exposed

- `max2021_health`  
  Returns adapter transport details and connectivity status.
- `max2021_execute`  
  Runs an arbitrary MaxScript snippet.
- `max2021_list_selected_nodes`  
  Returns selected node names.
- `max2021_list_all_nodes`  
  Returns top-level scene node names.

## Transport modes

- `pymxs` (in-process): easiest when the server runs from 3ds Max’s Python runtime.
- `socket` (external process): the server sends MaxScript to a bridge service over TCP.
- `auto`: tries `pymxs` first and falls back to socket mode.

## Launch

- stdio (default):  
  `python scripts/mcp/start_max2021_mcp_stdio.py`
- with explicit mode/env:  
  `python -m max2021_mcp --mode stdio --adapter socket --maxscript-host 127.0.0.1 --maxscript-port 19001`

## Environment variables

- `MAX2021_MCP_MODE` (`auto|pymxs|socket`)
- `MAX2021_MCP_HOST` (default `127.0.0.1`)
- `MAX2021_MCP_PORT` (default `19001`)
- `MAX2021_MCP_TIMEOUT_SECONDS` (default `3.0`)

When socket mode is used, you must provide a MaxScript-side service that accepts
JSON requests and returns `{"text": "..."}` 
for the current socket adapter.

## 3ds Max 2021 listener plugin

Drop the plugin in your 3ds Max 2021 startup scripts folder:

- `scripts/max2021_mcp/max2021_mcp_bridge.ms`
- Copy to `<3ds Max install path>\\scripts\\Startup\\max2021_mcp_bridge.ms`

Then set these environment variables before launching 3ds Max (or update the
defaults in the plugin):

- `MAX2021_MCP_HOST` (default `127.0.0.1`)
- `MAX2021_MCP_PORT` (default `19001`)

After Max starts, the script starts a background TCP listener on that host/port and
accepts MaxScript payloads in the form:

```json
{"id":"max2021-...","script":"format \"Hello from MCP\\n\""}
```

The response shape is:

```json
{"id":"max2021-...","text":"result text","is_error":false}
```

Useful runtime commands in MaxScript console:

- `max2021McpBridgeStart()`
- `max2021McpBridgeStop()`
- `max2021McpBridgeGetStatus()`
