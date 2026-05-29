# Body Attachment System Model Recipes

This folder stores lightweight `.json` builds created by the Body Attachment
System (BAS). A build records how a preview model was assembled: the base body,
the attached head or equipment layers, the target sockets, layer transforms, and
the runtime rules needed to rebuild the same BAS layout.

The runtime contract for how BAS layers attach, animate, and stay isolated from
body skinning is documented in `../README.md`. Treat that contract as the base
for every BAS model recipe.

BAS recipes do not store copied mesh, animation, texture, MDL, or MDX data. They
reference source game assets by game and resref so the preview can be rebuilt
from the installed KOTOR resources.

## JSON Shape

Each recipe uses the `ghostrigger.bas.model` schema and currently stores:

- `game`: source game used for the body and attachments, such as `K1` or `K2`.
- `body`: the base body resref/name/supermodel.
- `layers`: ordered BAS layers for `BODY`, `HEAD`, `L. HAND`, `R. HAND`,
  `L. Weapon`, and `R. Wep`.
- `layers[].transform`: per-layer local position, rotation quaternion, and scale
  relative to the socket. These values are preserved so heads and equipment can
  later get alignment/tweak controls without changing the file format.
- `attachments`: compact slot-to-resref map for attached layers.
- `runtime`: notes that attachments are socket followers, body animations stay
  owned by the body, and attachment skinning is isolated from the body palette.

Hand slots are sockets only. Actual weapon models belong in `left_weapon` and
`right_weapon`, which follow the `lhand` and `rhand` dummy/socket nodes.

## Generated Files

Files are named from the game, body resref, and attached layer resrefs, for
example:

```text
k1_p_carthbb_pmha01_w_blstrpstl_001.json
```

Use the BAS toolbox `Save Build` button to choose a model/build name. Opening
one of these `.json` files through the normal model-open flow reimports the BAS
build as its own composed preview model, while still resolving the source pieces
from the installed game assets.

Saving the same build name updates the same JSON file. These files are intended
to be human-readable and safe to diff.
