# 3ds Max 2021 MCP bridge plugin

This folder contains a listener plugin that runs inside 3ds Max 2021 and executes
received MaxScript payloads for the GhostRigger `max2021-mcp` server in socket
mode.

## Files

- `max2021_mcp_bridge.ms`: startup-friendly MaxScript listener that:
  - binds to `MAX2021_MCP_HOST` / `MAX2021_MCP_PORT`,
  - accepts one JSON request per connection,
  - executes the `script` field with MaxScript `execute`, and
  - returns JSON response text to the MCP socket client.

## Install

1. Copy `max2021_mcp_bridge.ms` into your 3ds Max startup folder:
   `C:\Program Files\Autodesk\3ds Max 2021\scripts\Startup\`
   (or user-level startup folder:
   `%LOCALAPPDATA%\Autodesk\3ds Max\2021 - 64bit\ENU\scripts\Startup\`)
2. Optional environment values before launching Max:
   - `MAX2021_MCP_HOST=127.0.0.1`
   - `MAX2021_MCP_PORT=19001`
3. Start 3ds Max. The bridge auto-starts by default and prints bind status to the
   MaxScript Listener.

## Manual control

Open the MaxScript Listener and run:

- `max2021McpBridgeStart()`
- `max2021McpBridgeStop()`
- `max2021McpBridgeGetStatus()`

## Protocol

Input payload from the MCP server:

```json
{"id":"max2021-<request-id>","script":"<maxscript body>"}
```

Output to MCP:

```json
{"id":"max2021-<request-id>","text":"<execution output>","is_error":false}
```

If execution fails, `is_error` is `true` and `text` includes the MaxScript error.

## Note

The listener is intentionally small and transport-focused for research parity.
Any modeling/tooling abstractions should stay in your GhostRigger-side Python MCP
or adapter layers.
