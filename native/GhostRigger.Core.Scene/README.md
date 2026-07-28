# GhostRigger.Core.Scene

Merged namespace package boundary.

Owner: LordVaderCW

## Current Python ownership

The operative Scene Python sources are package-local under
`native/GhostRigger.Core.Scene/Python/src/`. In particular,
`core/scene/spatial_snapshot.py` is the Scene-owned source of truth for stable
object identity, transform and pivot serialization, coordinate-system
declarations, and deterministic scene revisions. A matching root
`src/core/scene` source tree is not present in this branch.

The generated payload manifest still records logical `src/...` paths and
`originals_remain_in_src: true`; for package-local modules this is legacy
metadata and must not be treated as proof of a second canonical copy.

GUI code may add observed viewport, camera, grid, and capture data, but it must
compose those observations through the Scene serializer. Screenshots remain
visual evidence and do not prove an action that was not observed semantically.

After Scene-owned Python changes, regenerate only
`GhostRigger.Core.Scene` and run the focused spatial-contract and native
payload identity tests.
