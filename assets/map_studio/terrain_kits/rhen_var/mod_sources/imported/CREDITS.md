# Authorized Rhen Var Source Credits

Ghost Studio includes a curated subset of the user-supplied Rhen Var mod
archives under author permission confirmed by the user on 2026-07-25. This
record does not assert a general public license. Underlying Star Wars and source
mod rights remain with their respective creators and rights holders.

## Rhen Var: Citadel - Test Release 1

- Author: Calrissian97
- Archive: `RhenVarCitadelBothVersions.rar`
- SHA-256: `a955db411ed09aa78ce3f8c6e410568592432b613e79b1fa698573af74668753`
- Original credits: Gametoast Community and SWBFGamers.

## Rhen Var: Colony 1.1

- Author: Jerbot77
- Archive: `RhenVarColony.7z`
- SHA-256: `b4656a280ce0edc571aa3adf6b93d5030ebdea8bcfaac1ed24cb3e8e3f7a1557`
- Original credits: Fierfek's Mapmaking Guide.
- The supplied readme prohibits reuse without permission; the user explicitly
  confirmed mod-author permission for this Ghost Studio packaging.

## Rhen Var: Temple v2.0

- Author: [SBF]DannBoeing
- Archive: `rhenvartemple2.0.zip`
- SHA-256: `63d6807e347efa5da424e3800dd1b46d63e76db45708f0c2ed9737a0e46ee3c1`
- Original credits: LucasArts, Psych0fred, [GT]Gogie,
  MetalcoreRancor/Snake, Phazon_Elite, and the Gametoast community.

## Conversion Record

Visual render meshes were extracted to GLB with `swbf-unmunge` 1.3.0,
normalized in Blender 4.2 to metres/Z-up, and packaged as OBJ/MTL with
power-of-two diffuse TGAs. High-detail render geometry, UV0, normals, material
assignments, and diffuse alpha were retained. Source low-resolution, collision,
and shadow-volume nodes were intentionally excluded from visual geometry.
Runtime collision intent is declared per asset in the pack manifest.
