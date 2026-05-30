"""TXI metadata parsing and material helpers for frame rendering."""

from __future__ import annotations

from .dependencies import *  # noqa: F401,F403
from .math_helpers import _clean_tex_name
from .tpc import _extract_txi_from_tpc

# ─────────────────────────────────────────────────────────────────────
#  TXI Metadata Parser
#  Parses KotOR TXI ASCII command-value pairs into a structured dict.
#  Reference: PyKotor txi_data.py, KotOR.js TXI.ts, NWN wiki TXI docs.
# ─────────────────────────────────────────────────────────────────────

def _parse_txi_string(txi: str) -> dict:
    """
    Parse a TXI metadata string into a dictionary of properties.

    TXI files are ASCII text files with command-value pairs:
        proceduretype cycle
        numx 4
        numy 4
        fps 10
        cube 1
        bumpmap some_texture
        bumpmapscaling 1.5
        blending additive
        envmaptexture cm_fog

    Returns a dict with these keys (with sensible defaults if absent):
        blending      : int   (0=none, 1=additive, 2=punchthrough)
        cube          : bool
        proceduretype : str   ('cycle', 'water', 'arturo', '')
        numx          : int   (flipbook columns)
        numy          : int   (flipbook rows)
        fps           : float (flipbook animation fps)
        envmaptexture : str
        bumpmaptexture: str
        bumpmapscaling: float
        rotate        : float (degrees)
        loop          : bool
        clamp_s       : bool  (True = GL_CLAMP_TO_EDGE in S/U axis)
        clamp_t       : bool  (True = GL_CLAMP_TO_EDGE in T/V axis)
        clamp         : bool  (True = clamp both S and T axes)
        decal         : bool
        mipmap        : int   (0=off, 1=on)
        filter        : bool
        downsamplemax : int
        downsamplemin : int
        xbox_downsample: int  (Xbox-specific downsampling override)
        compresstexture: bool (request driver-level texture compression)
        isbumpmap     : bool
        islightmap    : bool
        diffusebumpmap: str
        specbumpmap   : str
        distort       : bool
        distortangle  : float
        distortspeed  : float
        renderhint    : str   ('animatedmodel', 'normalmap', 'specularmap', '')
        priority      : int   (render priority, 0=default)
        texture_op    : str   (texture blending operation, '')
    """
    result = {
        'blending': 0,
        'cube': False,
        'proceduretype': '',
        'numx': 0,
        'numy': 0,
        'fps': 0.0,
        'envmaptexture': '',
        'bumpmaptexture': '',
        'bumpmapscaling': 1.0,
        'rotate': 0.0,
        'loop': True,
        'clamp_s': False,
        'clamp_t': False,
        'decal': False,
        'mipmap': 1,
        'filter': True,
        'downsamplemax': 0,
        'downsamplemin': 0,
        'isbumpmap': False,
        'islightmap': False,
        'diffusebumpmap': '',
        'specbumpmap': '',
        'distort': False,
        'distortangle': 0.0,
        'distortspeed': 0.0,
        'clamp': False,
        'xbox_downsample': 0,
        'compresstexture': False,
        'renderhint': '',
        'priority': 0,
        'texture_op': '',
        # Additional KotOR TXI commands
        'wateralpha': 1.0,       # Water/transparency alpha multiplier (0.0-1.0)
        'specularcolour': '',    # Specular highlight color texture name
        'fontwidth': 0,          # GUI font glyph width
        'fontheight': 0,         # GUI font glyph height
        'spacingr': 0.0,         # GUI font right-spacing
        'spacingb': 0.0,         # GUI font bottom-spacing
        'numchars': 0,           # GUI font character count
        'basetexture': '',       # Base texture reference
        'defaultwidth': 0,       # Default width for procedural textures
        'defaultheight': 0,      # Default height for procedural textures
        'channelscale': (1.0, 1.0, 1.0, 1.0),  # RGBA channel scale (per-channel)
        'channeltranslate': (0.0, 0.0, 0.0, 0.0),  # RGBA channel translation
    }
    if not txi:
        return result

    # Multi-line coordinate commands (upperleftcoords / lowerrightcoords)
    # These consume the next N lines after the command.
    _coord_mode = None
    _coord_rem = 0

    for raw_line in txi.splitlines():
        line = raw_line.strip()
        if not line:
            continue

        # Handle multi-line coordinate blocks
        if _coord_mode is not None:
            _coord_rem -= 1
            if _coord_rem <= 0:
                _coord_mode = None
            continue

        # Split into command and optional argument
        parts = line.split(None, 1)
        if not parts:
            continue
        cmd = parts[0].lower()
        arg = parts[1].strip() if len(parts) > 1 else ''

        try:
            if cmd == 'blending':
                s = arg.lower()
                if s == 'additive':
                    result['blending'] = 1
                elif s in ('punchthrough', 'punch-through'):
                    result['blending'] = 2
                else:
                    result['blending'] = int(arg) if arg.isdigit() else 0
            elif cmd == 'cube':
                result['cube'] = bool(int(arg)) if arg else True
            elif cmd == 'proceduretype':
                result['proceduretype'] = arg.lower()
            elif cmd == 'numx':
                result['numx'] = int(arg)
            elif cmd == 'numy':
                result['numy'] = int(arg)
            elif cmd == 'fps':
                result['fps'] = float(arg)
            elif cmd in ('envmaptexture', 'env_map_texture'):
                # FIX-ENVMAP: envmaptexture and bumpyshinytexture both specify the
                # reflection/environment-map companion texture for the diffuse layer.
                # Reference: KotOR.js TXI.ts:161-164, xoreos modelnode.cpp:479-482.
                result['envmaptexture'] = arg.lower()
            elif cmd in ('bumpmaptexture', 'bumpmap'):
                result['bumpmaptexture'] = arg.lower()
            elif cmd == 'bumpmapscaling':
                result['bumpmapscaling'] = float(arg)
            elif cmd == 'rotate':
                result['rotate'] = float(arg)
            elif cmd == 'loop':
                result['loop'] = bool(int(arg)) if arg else True
            elif cmd in ('clamps', 'clamp_s'):
                result['clamp_s'] = bool(int(arg)) if arg else True
            elif cmd in ('clampt', 'clamp_t'):
                result['clamp_t'] = bool(int(arg)) if arg else True
            elif cmd == 'clamp':
                # KotOR 'clamp' is a bitmask per xoreos textures/txi.cpp and PyKotor:
                #   bit 0 (value & 1) = clamp S axis (U)
                #   bit 1 (value & 2) = clamp T axis (V)
                # So: clamp 1 → S only, clamp 2 → T only, clamp 3 → both axes
                # The only value seen in real K1/K2 data is 3 (both axes clamped).
                # clamp 0 → no clamping (same as omitting the command).
                try:
                    val_int = int(arg) if arg else 3  # default 3 when no arg
                except (ValueError, TypeError):
                    val_int = 3
                clamp_s_bit = bool(val_int & 1)
                clamp_t_bit = bool(val_int & 2)
                result['clamp'] = bool(val_int)
                result['clamp_s'] = clamp_s_bit
                result['clamp_t'] = clamp_t_bit
            elif cmd == 'decal':
                result['decal'] = bool(int(arg)) if arg else True
            elif cmd == 'mipmap':
                result['mipmap'] = int(arg) if arg else 1
            elif cmd == 'filter':
                result['filter'] = bool(int(arg)) if arg else True
            elif cmd == 'downsamplemax':
                result['downsamplemax'] = int(arg)
            elif cmd == 'downsamplemin':
                result['downsamplemin'] = int(arg)
            elif cmd == 'xbox_downsample':
                # Xbox-specific downsampling override (reduces texture res on Xbox)
                result['xbox_downsample'] = int(arg) if arg else 1
            elif cmd in ('compresstexture', 'compress'):
                # Request driver-level texture compression (DXTn hint)
                result['compresstexture'] = bool(int(arg)) if arg else True
            elif cmd == 'renderhint':
                # Rendering hint ('animatedmodel', 'normalmap', 'specularmap')
                result['renderhint'] = arg.lower()
            elif cmd == 'priority':
                # Render priority (0=default, higher = render later)
                result['priority'] = int(float(arg)) if arg else 0
            elif cmd in ('texop', 'texture_op', 'textureop'):
                # Texture blending op ('modulate', 'add', 'decal', etc.)
                result['texture_op'] = arg.lower()
            elif cmd == 'isbumpmap':
                result['isbumpmap'] = bool(int(arg)) if arg else True
            elif cmd == 'islightmap':
                result['islightmap'] = bool(int(arg)) if arg else True
            elif cmd in ('isdiffusebumpmap', 'diffusebumpmap'):
                if arg and not arg.lstrip('-').replace('.', '').isdigit():
                    result['diffusebumpmap'] = arg.lower()
                else:
                    result['isbumpmap'] = True
            elif cmd == 'bumpyshinytexture':
                # KotOR/xoreos: bumpyshinytexture is an ALIAS for envmaptexture.
                # Both KotOR.js (TXI.ts:161-164) and xoreos (modelnode.cpp:479-482)
                # treat this as the environment-map companion texture.
                # Do NOT treat it as a bump map — it is a reflection/env map.
                if arg and not arg.lstrip('-').replace('.', '').isdigit():
                    result['envmaptexture'] = arg.lower()
                # else: malformed line, skip
            elif cmd in ('isspecularbumpmap', 'specularbumpmap'):
                if arg and not arg.lstrip('-').replace('.', '').isdigit():
                    result['specbumpmap'] = arg.lower()
                else:
                    result['isbumpmap'] = True
            elif cmd == 'distort':
                result['distort'] = bool(int(arg)) if arg else True
            elif cmd == 'distortangle':
                result['distortangle'] = float(arg)
            elif cmd == 'distortspeed':
                result['distortspeed'] = float(arg)
            elif cmd in ('upperleftcoords', 'lowerrightcoords'):
                # These commands are followed by N coordinate lines
                try:
                    _coord_rem = int(arg)
                    _coord_mode = cmd
                except (ValueError, TypeError):
                    pass
            elif cmd == 'wateralpha':
                result['wateralpha'] = float(arg) if arg else 1.0
            elif cmd in ('specularcolour', 'specularcolor'):
                result['specularcolour'] = arg.lower() if arg else ''
            elif cmd == 'fontwidth':
                result['fontwidth'] = int(arg) if arg else 0
            elif cmd == 'fontheight':
                result['fontheight'] = int(arg) if arg else 0
            elif cmd == 'spacingr':
                result['spacingr'] = float(arg) if arg else 0.0
            elif cmd == 'spacingb':
                result['spacingb'] = float(arg) if arg else 0.0
            elif cmd == 'numchars':
                result['numchars'] = int(arg) if arg else 0
            elif cmd == 'basetexture':
                result['basetexture'] = arg.lower() if arg else ''
            elif cmd == 'defaultwidth':
                result['defaultwidth'] = int(arg) if arg else 0
            elif cmd == 'defaultheight':
                result['defaultheight'] = int(arg) if arg else 0
            elif cmd == 'channelscale':
                # channelscale has 4 float values on the next line as a block
                # For now just mark it as encountered; the coordinate block parser handles it
                pass
            elif cmd == 'channeltranslate':
                pass
            # Silently ignore unknown commands (many TXI commands are display hints)
        except (ValueError, TypeError, IndexError):
            pass

    return result


def _extract_alpha_test_from_tpc(raw_bytes: bytes) -> float:
    """Extract the alpha_test_threshold float from TPC header bytes [4-7].

    KotOR TPC header layout (Aurora engine):
      [0-3]  uint32  data_sz
      [4-7]  float   alpha_test_threshold  (0.0 = ignore, >0 = discard threshold)
      [8-9]  uint16  width
      [10-11]uint16  height
      [12]   uint8   encoding
      ...

    Used only for blending=punchthrough surfaces (TXI 'blending punchthrough').
    The engine's GL_ALPHA_TEST reference value; values above this pass the test.

    References:
        Kotor.NET KotorModelLoader.cs — reads TransparencyHint at +84 (mesh),
        alpha_test float from TPC header [4-7].
        xoreos tpc.cpp — alpha_test_threshold at offset 4.
        PyKotor io_tpc.py — alpha_test field in TPCHeader struct.

    Returns:
        float alpha_test_threshold (0.0..1.0). Default 0.5 if not present.
    """
    if not raw_bytes or len(raw_bytes) < 8:
        return 0.5
    try:
        at = struct.unpack_from('<f', raw_bytes, 4)[0]
        if 0.0 < at <= 1.0:
            return at
    except Exception:
        pass
    return 0.5


def _apply_txi_to_node(node, txi_str: str, alpha_test: float = 0.5) -> None:
    """
    Parse a TXI string and apply the metadata fields to a ModelNode.

    Called after loading a texture so that TXI data from TPC embedded
    metadata (or a standalone .txi file) updates the node's rendering
    properties.  Only fields that have explicit TXI entries are updated;
    other node fields remain at their ModelNode defaults.

    Args:
        node      : ModelNode instance to update
        txi_str   : Raw TXI ASCII string (may be empty)
        alpha_test: Per-node punchthrough threshold from TPC header [4-7].
                    FIX-ALPHATEST: Stored on node.txi_alpha_test so the GPU
                    renderer can pass it as u_alpha_test per draw-call instead
                    of using the hardcoded 0.5 global default.
                    Default: 0.5 (matches Aurora engine default).
    """
    # Always store alpha_test on node (even if txi_str is empty —
    # punchthrough threshold comes from TPC header, not TXI content).
    if hasattr(node, 'txi_alpha_test'):
        node.txi_alpha_test = float(alpha_test) if 0.0 < alpha_test <= 1.0 else 0.5

    if not txi_str:
        return
    meta = _parse_txi_string(txi_str)

    # Blending / transparency
    if meta['blending']:
        node.txi_blending = meta['blending']

    # Cubemap flag
    if meta['cube']:
        node.txi_cube = True

    # Flipbook animation
    if meta['proceduretype']:
        node.txi_proceduretype = meta['proceduretype']
    if meta['numx'] > 0:
        node.txi_numx = meta['numx']
    if meta['numy'] > 0:
        node.txi_numy = meta['numy']
    if meta['fps'] > 0.0:
        node.txi_fps = meta['fps']

    # Companion textures
    # FIX-ENVMAP: envmaptexture and bumpyshinytexture both name the env-map companion.
    # _parse_txi_string already maps bumpyshinytexture → result['envmaptexture'],
    # so both keywords are handled via the same field here.
    if meta['envmaptexture']:
        node.txi_envmaptexture = meta['envmaptexture']
    if meta['bumpmaptexture']:
        node.txi_bumpmaptexture = meta['bumpmaptexture']
        node.bump_map = meta['bumpmaptexture']  # also update the bump_map field
    if meta['bumpmapscaling'] != 1.0:
        node.txi_bumpmapscaling = meta['bumpmapscaling']

    # UV rotation from TXI (additional to rotate_texture flag)
    if meta['rotate'] != 0.0:
        node.txi_rotate = meta['rotate']

    # Loop
    node.txi_loop = meta['loop']

    # Clamp modes (clamp sets both axes; individual overrides respected too)
    if meta['clamp']:
        node.txi_clamp_s = True
        node.txi_clamp_t = True
    if meta['clamp_s']:
        node.txi_clamp_s = True
    if meta['clamp_t']:
        node.txi_clamp_t = True

    # Water alpha (modulates texture transparency for water/lava surfaces)
    if meta.get('wateralpha', 1.0) != 1.0:
        node.txi_wateralpha = meta['wateralpha']

    # Specular colour map (bumpyshinytexture / specularcolour)
    if meta.get('specularcolour'):
        node.txi_specularcolour = meta['specularcolour']

    # Decal: TXI decal flag — surface is a decal (alpha as blend weight over bg)
    if meta.get('decal'):
        node.txi_decal = True

    # Bump/normal-map flag — this texture slot IS a bump/normal map
    if meta.get('isbumpmap'):
        node.txi_isbumpmap = True

    # Lightmap flag — this texture slot IS a lightmap
    if meta.get('islightmap'):
        node.txi_islightmap = True


def _compute_flipbook_uv(u: float, v: float, numx: int, numy: int,
                          frame: int) -> tuple:
    """
    Compute UV coordinates within a flipbook (sprite-sheet) texture frame.

    Flipbook textures tile the sprite sheet into numx × numy cells.
    Frame 0 is top-left, frame (numx-1) is top-right, frame (numx*(numy-1))
    is bottom-left (matching KotOR.js TXI.ts cell ordering convention).

    Args:
        u, v  : Original UV coords (0..1 within the full sprite sheet)
        numx  : Number of columns
        numy  : Number of rows
        frame : Current animation frame index (0-based)

    Returns:
        (u_out, v_out): UV within the specific cell for this frame
    """
    if numx <= 0 or numy <= 0:
        return u, v
    # Clamp frame to valid range
    total_frames = numx * numy
    frame = frame % total_frames

    col = frame % numx
    row = frame // numx

    cell_w = 1.0 / numx
    cell_h = 1.0 / numy

    # u, v within [0,1] map to the sub-cell
    u_out = (col + (u % 1.0)) * cell_w
    v_out = (row + (v % 1.0)) * cell_h
    return u_out, v_out


__all__ = tuple(name for name in globals() if not name.startswith('__'))
