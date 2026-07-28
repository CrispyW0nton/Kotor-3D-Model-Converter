# GhostRigger.Core.Automation

Owner: LordVaderCW

Owner surfaces:

- Legacy Ghostworks IPC and broad KotorMCP compatibility.
- The narrow authenticated Ghost Studio spatial bridge used by MCPStudio.
- MCP validation and native automation boundary metadata.

## Current Python ownership

The operative Automation Python sources are package-local under
`native/GhostRigger.Core.Automation/Python/src/`. The root-level logical
sources named by the generated payload manifest (`src/ipc`, `src/kotormcp`,
and `src/ghoststudio_spatial_mcp`) are not present in this branch. Until those
canonical roots are deliberately restored, the package-local files are the
authoritative sources and must not be overwritten from an assumed root copy.

The generated manifest's `originals_remain_in_src` field is therefore legacy
metadata for these paths, not evidence that a matching root file exists.

## MCPStudio spatial boundary

`scripts/mcp/start_ghoststudio_spatial_stdio.py` launches only
`ghoststudio_spatial_mcp`. Its fixed catalog is:

- `ghoststudio_health`
- `ghoststudio_spatial_snapshot`
- `ghoststudio_capture`
- `ghoststudio_evidence_gaps`

The child reads a private, expiring session descriptor and signs the exact
HTTP method, loopback path, timestamp, nonce, and body digest. The GUI rejects
missing, invalid, stale, and replayed signatures. The child accepts no remote
host, arbitrary URL, arbitrary file path, redirects, proxy settings, or broad
KotorMCP dispatch.

The legacy Ghostworks and KotorMCP routes are outside this narrow
authentication boundary. Securing the spatial route does not make those
legacy routes trusted or production-forwardable.

## Native boundary

- Bridge method: C ABI DLL.
- C++ owns Phase 1 module-boundary metadata, dependency-scan metadata, and
  native-readiness diagnostics.
- Python owns runtime behavior, object lifetimes, workflow policy, IPC
  request validation, and session authentication.

## Verification

- Compile changed Python modules before payload generation.
- Regenerate only `GhostRigger.Core.Automation` with
  `scripts/native_python_payload_generator.py GhostRigger.Core.Automation`.
- Run the focused spatial adapter, IPC compatibility, secret-hygiene, and
  native-payload identity tests.
- A visible app check is required before claiming live GUI integration.
