# Ghost Studio Rhen Var Optional Asset Pack

This branch is a data-only overlay for Ghost Studio. It contains no application
source, native payloads, configuration, tests, or project files.

## Install

1. Install Ghost Studio from the `ghost-studio` branch at commit `ed52ee43` or
   newer.
2. Download this branch with **Code > Download ZIP** and extract it.
3. Open the extracted `Ghost-Studio-codex-rhen-var-optional-kit` folder.
4. Drag the `assets` folder into the root of your Ghost Studio installation and
   allow Windows to merge the folders.
5. Restart Ghost Studio if it was already running.

The final manifest must be located at:

`<Ghost Studio root>/assets/map_studio/terrain_kits/rhen_var/manifest.json`

Do not place the outer GitHub ZIP folder inside the Ghost Studio root; doing so
creates an extra directory level that Map Studio cannot discover.

## Upgrade or remove

Installing a newer copy can be done with the same folder-merge operation. To
remove the optional pack, close Ghost Studio and remove only:

`assets/map_studio/terrain_kits/rhen_var`

## Credits and permissions

Asset authorship, source hashes, conversion history, and permission records are
stored in `manifest.json`, `mod_sources/imported/CREDITS.md`, and the associated
provenance files. Those records travel with the pack and must be retained.
