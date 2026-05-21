#!/usr/bin/env python3
"""
build_game_templates.py — Regenerate GhostRigger template MDL files from
real KotOR game data.

Instead of hand-crafting bone coordinates, we:
1. Load an actual game model binary MDL/MDX from the BIF archives.
2. Parse it to a KotorModel.
3. Strip all geometry (vertices/faces/normals/UVs/skin weights) to produce
   a pure-skeleton (all-dummy) template.
4. Rename the model and its root node.
5. Save as ASCII MDL.

Source models chosen:
  K1 body  →  pfbcm  (Female Commoner – Medium)  super=S_Female03
  K1 head  →  pfhc01 (Female Human Head 01)       super=S_Female03
  K2 body  →  pfbcm  (K2 version of same model)   super=S_Female03
  K2 head  →  pfhc01 (K2 version)                  super=S_Female03

This gives templates with the exact real game skeleton hierarchy.
"""

from __future__ import annotations
import os, sys, json, logging
from pathlib import Path

logging.basicConfig(level=logging.INFO, format='%(levelname)s %(message)s')
log = logging.getLogger('build_game_templates')

REPO = Path(__file__).parent
sys.path.insert(0, str(REPO))

from src.core.qt_core.game.kotor_install import KotorInstallation
from src.core.qt_core.mdl.mdl_parser import MDLBinaryParser, MDLAsciiWriter, MDLAsciiParser
from src.core.qt_core.geometry.model_data import NodeFlags

# ── Where to find the game data ───────────────────────────────────────────────
K1_DIR = str(REPO / 'game_data' / 'k1_extracted')
K2_DIR = str(REPO / 'game_data' / 'k2_extracted')
OUT_DIR = str(REPO / 'templates')

# ── Source model selections ───────────────────────────────────────────────────
# (source_resref, output_name, game, part, description)
TEMPLATES = [
    ('pfbcm',  'gr_body_k1', 'K1', 'body',
     'K1 Female Commoner Body (Medium) — real pfbcm skeleton, stripped to dummies'),
    ('pfhc01', 'gr_head_k1', 'K1', 'head',
     'K1 Female Human Head 01 — real pfhc01 skeleton, stripped to dummies'),
    ('pfbcm',  'gr_body_k2', 'K2', 'body',
     'K2 Female Commoner Body (Medium) — real K2 pfbcm skeleton, stripped to dummies'),
    ('pfhc01', 'gr_head_k2', 'K2', 'head',
     'K2 Female Human Head 01 — real K2 pfhc01 skeleton, stripped to dummies'),
]

# ── Helpers ───────────────────────────────────────────────────────────────────

def strip_to_skeleton(node):
    """
    Recursively convert every non-dummy node to a pure dummy (skeleton-only).
    Preserves: name, parent/children links, position, rotation.
    Removes:   vertices, faces, normals, UVs, skin weights, texture refs.
    """
    DUMMY_FLAGS = int(NodeFlags.HEADER)   # 1 == dummy node
    if node.type_label not in ('dummy', 'reference'):
        node.vertices      = []
        node.faces         = []
        node.normals       = []
        node.uvs           = []
        # skin-weight arrays may be named differently per KotorModel impl
        for attr in ('skin_weights', 'bone_indices', 'bone_weights',
                     'constraint_weights', 'dangly_constraints'):
            if hasattr(node, attr):
                setattr(node, attr, [])
        node.texture       = ''
        node.bitmap        = ''
        node.flags         = DUMMY_FLAGS
    for child in node.children:
        strip_to_skeleton(child)


def collect_node_info(root):
    """Return list of (name, type, parent_name) for every node."""
    results = []
    stack = [(root, None)]
    while stack:
        node, parent = stack.pop()
        results.append({
            'name':   node.name,
            'type':   node.type_label,
            'parent': parent.name if parent else 'NULL',
            'pos':    list(getattr(node, 'position', (0, 0, 0))),
        })
        for c in reversed(node.children):
            stack.append((c, node))
    return results


def build_manifest(model, source_resref: str, game: str, part: str,
                   description: str, node_info: list) -> dict:
    return {
        'name':         model.name,
        'source_model': source_resref.upper(),
        'game_version': game,
        'part':         part,
        'supermodel':   model.supermodel,
        'classification': getattr(model, 'classification', 'character'),
        'description':  description,
        'node_count':   model.node_count(),
        'nodes':        node_info,
        'note': (
            'Skeleton-only template derived from a real KotOR game model. '
            'All geometry stripped; only dummy nodes remain for easy rigging.'
        ),
    }


def generate_template(inst: KotorInstallation, source_resref: str,
                      out_name: str, game: str, part: str,
                      description: str, out_dir: str):
    log.info('Loading %s from %s install…', source_resref, game)
    mdl_bytes = inst.get_mdl(source_resref)
    mdx_bytes = inst.get_mdx(source_resref) or b''
    if not mdl_bytes:
        raise RuntimeError(f'{source_resref} not found in {game} install')

    model = MDLBinaryParser(mdl_bytes, mdx_bytes).parse()
    log.info('  Parsed: name=%s  super=%s  nodes=%d  anims=%d',
             model.name, model.supermodel, model.node_count(), len(model.animations))

    # Strip all geometry
    strip_to_skeleton(model.root_node)

    # Rename root node and model
    model.root_node.name = out_name
    model.name = out_name

    # Clear any animations (body models have none; head supermodels might)
    model.animations = []

    # Recompute bounds (no geometry → trivial)
    if hasattr(model, 'compute_bounds'):
        model.compute_bounds()

    node_info = collect_node_info(model.root_node)

    # Write ASCII MDL
    os.makedirs(out_dir, exist_ok=True)
    mdl_path = os.path.join(out_dir, out_name + '.mdl')
    MDLAsciiWriter().write(model, mdl_path)
    mdl_size = os.path.getsize(mdl_path)
    log.info('  Written %s (%d bytes)', mdl_path, mdl_size)

    # Verify round-trip
    with open(mdl_path) as fh:
        lines = fh.readlines()
    m2 = MDLAsciiParser().parse(lines)
    assert m2.node_count() == model.node_count(), (
        f'Round-trip node count mismatch: {m2.node_count()} != {model.node_count()}')
    log.info('  Round-trip OK: %d nodes', m2.node_count())

    # Write manifest
    manifest = build_manifest(model, source_resref, game, part, description, node_info)
    json_path = os.path.join(out_dir, out_name + '_manifest.json')
    with open(json_path, 'w') as fh:
        json.dump(manifest, fh, indent=2)
    log.info('  Manifest: %s', json_path)

    return {'mdl': mdl_path, 'json': json_path,
            'nodes': model.node_count(), 'super': model.supermodel}


def main():
    os.makedirs(OUT_DIR, exist_ok=True)

    installs = {
        'K1': KotorInstallation(K1_DIR),
        'K2': KotorInstallation(K2_DIR),
    }

    results = []
    for source_resref, out_name, game, part, description in TEMPLATES:
        inst = installs[game]
        info = generate_template(
            inst, source_resref, out_name, game, part, description, OUT_DIR
        )
        results.append((out_name, info))

    print('\n=== Templates generated ===')
    for out_name, info in results:
        print(f'  {out_name}.mdl  nodes={info["nodes"]}  super={info["super"]}')

    # Update templates/README.md
    _write_readme(results)
    print(f'\nAll templates written to {OUT_DIR}/')


def _write_readme(results):
    lines = [
        '# GhostRigger Template Models\n',
        '\n',
        'Skeleton-only templates derived from **real KotOR game models** (binary MDL/MDX\n',
        'from the BIF archives), with all geometry stripped. The bone hierarchy,\n',
        'node names, positions, rotations, and supermodel references are 100% authentic.\n',
        '\n',
        '## Files\n',
        '\n',
        '| File | Game | Source | Nodes | Supermodel |\n',
        '|------|------|--------|-------|------------|\n',
    ]
    src_map = {
        'gr_body_k1': ('pfbcm', 'K1'), 'gr_head_k1': ('pfhc01', 'K1'),
        'gr_body_k2': ('pfbcm', 'K2'), 'gr_head_k2': ('pfhc01', 'K2'),
    }
    for out_name, info in results:
        src_resref, game = src_map.get(out_name, ('?', '?'))
        lines.append(
            f'| `{out_name}.mdl` | {game} | `{src_resref}` | {info["nodes"]} | `{info["super"]}` |\n'
        )
    lines += [
        '\n',
        '## Usage in GhostRigger\n',
        '\n',
        '1. Open the **Character Builder** tab.\n',
        '2. Click **Body Template K1/K2** or **Head Template K1/K2**.\n',
        '3. The template loads with its authentic skeleton highlighted in the viewport.\n',
        '4. Click **Select All Bones** to select the entire rig, or use the group\n',
        '   buttons (Spine, Arms, Legs, Head) for partial selection.\n',
        '5. Import your OBJ/FBX mesh and use **Apply Template Rig** to transfer the skeleton.\n',
        '6. Export as ASCII MDL.\n',
        '\n',
        '## Supermodel chain\n',
        '\n',
        '```\n',
        'K1/K2 body & head templates both reference S_Female03\n',
        '  S_Female03 → S_Female02 → S_Female01 → S_Male02 → S_Male01 → NULL\n',
        '```\n',
        '\n',
        'This is the standard KotOR humanoid supermodel chain — the same one used by\n',
        'almost every PC body/head model in both games.\n',
        '\n',
        '## Node hierarchy (example: body template)\n',
        '\n',
        '```\n',
        'gr_body_k1 [dummy]  ← root (renamed from PFBCM)\n',
        '  RArm [dummy]\n',
        '  Torso [dummy]\n',
        '  LArm [dummy]\n',
        '  RArm [dummy]\n',
        '    Torso [dummy]\n',
        '      Impact [dummy]\n',
        '        camerahook [dummy]\n',
        '      ...\n',
        '      LArm [dummy]\n',
        '        cutscenedummy [dummy]\n',
        '          rootdummy [dummy]\n',
        '            pelvis_g [dummy]\n',
        '              lthigh_g / rthigh_g [dummy]\n',
        '                lshin_g / rshin_g [dummy]\n',
        '                  lfoot_g / rfoot_g [dummy]\n',
        '              torso_g / torsoUpr_g [dummy]\n',
        '              rcollar_g / lcollar_g [dummy]\n',
        '              rbicep_g / lbicep_g [dummy]\n',
        '              rforearm_g / lforearm_g [dummy]\n',
        '              rhand / lhand [dummy]\n',
        '              finger chains ...\n',
        '              necklwr_g → neck_g → head_g [dummy]\n',
        '```\n',
    ]
    readme_path = os.path.join(OUT_DIR, 'README.md')
    with open(readme_path, 'w') as fh:
        fh.writelines(lines)
    log.info('README written: %s', readme_path)


if __name__ == '__main__':
    main()
