"""
KotOR-Style Icon Generator – Phase 19
Generates pixel-art icons in Bioware/Aurora engine aesthetic:
  - Deep navy/space-blue backgrounds (#0d0d1a)
  - Gold accent colour (#ffcc44) for primary shapes
  - Teal/cyan highlights (#44ccff) for secondary details
  - Red (#ff4444) for danger/close icons
  - Faint border glow (#2a2a5a)
  - Clean geometric pixel shapes
"""

from PIL import Image, ImageDraw, ImageFilter
import os, math

OUT_DIR = "src/gui/icons"
os.makedirs(OUT_DIR, exist_ok=True)

# ── Palette ───────────────────────────────────────────────────────────────────
BG      = (13,  13,  26,  255)   # deep navy
BG2     = (18,  18,  38,  255)   # slightly lighter
PANEL   = (26,  26,  56,  255)
BORDER  = (42,  42,  90,  200)
GOLD    = (255, 204,  68,  255)
GOLD2   = (230, 170,  30,  255)
TEAL    = ( 68, 204, 255,  255)
TEAL2   = ( 30, 140, 200,  255)
GREEN   = ( 68, 255, 136,  255)
RED     = (255,  68,  68,  255)
RED2    = (200,  30,  30,  255)
WHITE   = (224, 224, 255,  255)
GRAY    = (144, 144, 200,  200)
PURPLE  = (160,  80, 255,  255)
ORANGE  = (255, 136,  68,  255)
TRANS   = (  0,   0,   0,    0)

def new_icon(size):
    img = Image.new("RGBA", (size, size), TRANS)
    d   = ImageDraw.Draw(img)
    # subtle background circle
    pad = 1
    d.ellipse([pad, pad, size-1-pad, size-1-pad], fill=BG2, outline=BORDER)
    return img, d

def save(img, name, size):
    path = os.path.join(OUT_DIR, f"{name}_{size}.png")
    img.save(path)

def glow_dot(d, x, y, color, r=2):
    """Draw a bright dot with a soft glow."""
    r2 = r+2
    alpha_glow = (color[0], color[1], color[2], 80)
    d.ellipse([x-r2, y-r2, x+r2, y+r2], fill=alpha_glow)
    d.ellipse([x-r,  y-r,  x+r,  y+r],  fill=color)

def draw_border(d, size, color=BORDER):
    d.rectangle([0, 0, size-1, size-1], outline=color, width=1)

# ═══════════════════════════════════════════════════════════════════════════════
# Individual icon drawers
# ═══════════════════════════════════════════════════════════════════════════════

def icon_open(size):
    img, d = new_icon(size)
    s = size
    # Folder shape: body + flap
    fx, fy = 2, s//2
    fw, fh = s-4, s//2-1
    # folder body
    d.rectangle([fx, fy, fx+fw, fy+fh], fill=GOLD2, outline=GOLD)
    # folder tab
    d.rectangle([fx, fy-3, fx+fw//2, fy], fill=GOLD, outline=GOLD)
    # opening arrow inside
    ax = fx + fw//2
    ay = fy + fh//2
    d.polygon([(ax-2,ay+2),(ax+4,ay-1),(ax-2,ay-3)], fill=BG)
    glow_dot(d, fx+fw-3, fy+2, TEAL, 1)
    return img

def icon_autorig(size):
    img, d = new_icon(size)
    s = size
    cx, cy = s//2, s//2
    # Spine line
    d.line([(cx, 3), (cx, s-4)], fill=TEAL, width=2)
    # Bone joints
    for y in [4, cy-2, cy+3, s-5]:
        glow_dot(d, cx, y, GOLD, 2)
    # Shoulder arms
    d.line([(cx-4, cy-3), (cx+4, cy-3)], fill=GOLD2, width=2)
    # Hip arms
    d.line([(cx-3, cy+2), (cx+3, cy+2)], fill=GOLD2, width=2)
    return img

def icon_export(size):
    img, d = new_icon(size)
    s = size
    cx = s//2
    # Arrow pointing up-right (export out of box)
    d.polygon([(cx-3,s-5),(cx+3,s-5),(cx+3,cy-1),(cx+5,cy-1),(cx,4),(cx-5,cy-1),(cx-3,cy-1)],
              fill=GREEN) if False else None
    # Box at bottom
    d.rectangle([3, s-6, s-4, s-4], fill=TEAL2, outline=TEAL)
    # Up arrow
    mid = cx
    d.polygon([(mid,4),(mid-3,9),(mid-1,9),(mid-1,s-7),(mid+1,s-7),(mid+1,9),(mid+3,9)],
              fill=GREEN)
    return img

def icon_import(size):
    img, d = new_icon(size)
    s = size
    cx = s//2
    # Box at top
    d.rectangle([3, 3, s-4, 7], fill=TEAL2, outline=TEAL)
    # Down arrow  
    mid = cx
    d.polygon([(mid,s-4),(mid-3,s-9),(mid-1,s-9),(mid-1,7),(mid+1,7),(mid+1,s-9),(mid+3,s-9)],
              fill=ORANGE)
    return img

def icon_settings(size):
    img, d = new_icon(size)
    s = size
    cx, cy = s//2, s//2
    # Gear: outer ring
    d.ellipse([cx-6, cy-6, cx+6, cy+6], outline=TEAL, width=2)
    # Gear teeth (8 teeth)
    for i in range(8):
        angle = i * math.pi / 4
        tx = int(cx + 7*math.cos(angle))
        ty = int(cy + 7*math.sin(angle))
        d.ellipse([tx-1,ty-1,tx+1,ty+1], fill=TEAL)
    # Center dot
    d.ellipse([cx-2, cy-2, cx+2, cy+2], fill=GOLD)
    return img

def icon_refresh(size):
    img, d = new_icon(size)
    s = size
    cx, cy = s//2, s//2
    r = s//2 - 3
    # Circular arc (3/4 circle)
    d.arc([cx-r, cy-r, cx+r, cy+r], start=45, end=360, fill=TEAL, width=2)
    # Arrow head at end of arc
    ax = int(cx + r * math.cos(math.radians(45)))
    ay = int(cy + r * math.sin(math.radians(45)))
    d.polygon([(ax-3, ay-1),(ax+1,ay-3),(ax+1,ay+3)], fill=TEAL)
    glow_dot(d, cx, cy, GOLD, 1)
    return img

def icon_cloth(size):
    img, d = new_icon(size)
    s = size
    # Flowing cloth lines (wavy)
    for i, y in enumerate(range(4, s-3, 3)):
        wave = int(2 * math.sin(i * 1.2))
        color = TEAL if i % 2 == 0 else TEAL2
        d.line([(3, y+wave), (s-4, y-wave)], fill=color, width=1)
    # Top bar (hanging point)
    d.rectangle([3, 3, s-4, 5], fill=GOLD, outline=GOLD2)
    return img

def icon_modular(size):
    img, d = new_icon(size)
    s = size
    # Grid of 4 blocks (modular rooms)
    half = s//2
    gap = 2
    pad = 2
    for gx in range(2):
        for gy in range(2):
            x1 = pad + gx * (half - gap//2)
            y1 = pad + gy * (half - gap//2)
            x2 = x1 + half - gap - pad
            y2 = y1 + half - gap - pad
            color = TEAL if (gx+gy) % 2 == 0 else GOLD2
            d.rectangle([x1, y1, x2, y2], fill=color, outline=BORDER)
    # Center connector dots
    d.ellipse([half-2, half-2, half+2, half+2], fill=WHITE)
    return img

def icon_diag(size):
    img, d = new_icon(size)
    s = size
    # Magnifying glass
    r = s//3
    cx, cy = s//2 - 1, s//2 - 1
    d.ellipse([cx-r, cy-r, cx+r, cy+r], outline=TEAL, width=2)
    # Handle
    hx1 = int(cx + r * 0.7)
    hy1 = int(cy + r * 0.7)
    d.line([(hx1, hy1), (s-3, s-3)], fill=TEAL, width=2)
    # Bug symbol inside (cross / check)
    d.line([(cx-2,cy),(cx+2,cy)], fill=GOLD, width=1)
    d.line([(cx,cy-2),(cx,cy+2)], fill=GOLD, width=1)
    return img

def icon_texture(size):
    img, d = new_icon(size)
    s = size
    # Checkerboard texture
    tile = max(2, s//6)
    for ty in range(0, s, tile):
        for tx in range(0, s, tile):
            if (tx//tile + ty//tile) % 2 == 0:
                d.rectangle([tx+1, ty+1, min(tx+tile, s-2), min(ty+tile, s-2)], 
                            fill=TEAL2)
    # Diamond overlay
    cx, cy = s//2, s//2
    d.polygon([(cx,3),(s-3,cy),(cx,s-3),(3,cy)], outline=GOLD, width=1)
    return img

def icon_library(size):
    img, d = new_icon(size)
    s = size
    # Three books (vertical rectangles)
    bw = (s-8) // 3
    colors = [TEAL, GOLD, GREEN]
    for i, col in enumerate(colors):
        x1 = 3 + i*(bw+1)
        d.rectangle([x1, 3, x1+bw-1, s-4], fill=col, outline=BG2)
        # spine line
        d.line([(x1+1, 4), (x1+1, s-5)], fill=BG, width=1)
    return img

def icon_search(size):
    img, d = new_icon(size)
    s = size
    r = s//3
    cx, cy = s//2 - 2, s//2 - 2
    # Clean circle
    d.ellipse([cx-r, cy-r, cx+r, cy+r], outline=GOLD, width=2)
    # Handle
    hx1 = int(cx + r*0.7); hy1 = int(cy + r*0.7)
    d.line([(hx1, hy1), (s-3, s-3)], fill=GOLD, width=2)
    return img

def icon_skeleton(size):
    img, d = new_icon(size)
    s = size
    cx = s//2
    # Spine
    d.line([(cx,3),(cx,s-4)], fill=TEAL, width=1)
    # Joints at intervals
    joints = [3, s//4, s//2, 3*s//4, s-4]
    for jy in joints:
        glow_dot(d, cx, jy, GOLD, 2 if jy == s//2 else 1)
    # Arm bones at shoulder and hip
    sy = s//4
    d.line([(cx-4, sy),(cx+4, sy)], fill=GOLD2, width=2)
    hy = 3*s//4
    d.line([(cx-3, hy),(cx+3, hy)], fill=GOLD2, width=2)
    return img

def icon_props(size):
    img, d = new_icon(size)
    s = size
    # Properties panel: lines of text
    for i, y in enumerate(range(4, s-2, 4)):
        width = [s-8, s-12, s-10, s-16, s-10][i % 5]
        color = GOLD if i == 0 else (TEAL if i % 2 else GRAY)
        d.line([(4, y), (4+width, y)], fill=color, width=2)
    return img

def icon_anims(size):
    img, d = new_icon(size)
    s = size
    # Keyframe timeline: horizontal bar with diamonds
    by = s//2
    d.line([(3, by), (s-4, by)], fill=TEAL, width=2)
    # Keyframe diamonds at positions
    for kx in [5, s//3+2, 2*s//3, s-5]:
        d.polygon([(kx,by-3),(kx+3,by),(kx,by+3),(kx-3,by)], fill=GOLD)
    # Play triangle
    tx = s//2
    d.polygon([(tx-2,4),(tx+4,7),(tx-2,10)], fill=GREEN)
    return img

def icon_rig(size):
    img, d = new_icon(size)
    s = size
    # Chain link icon (rig = connections)
    cx, cy = s//2, s//2
    # Two linked circles
    r = s//4
    d.ellipse([3, cy-r, 3+r*2, cy+r], outline=TEAL, width=2)
    d.ellipse([s-3-r*2, cy-r, s-3, cy+r], outline=GOLD, width=2)
    # Link bar
    d.line([(3+r, cy), (s-3-r, cy)], fill=WHITE, width=2)
    return img

def icon_normalmap(size):
    img, d = new_icon(size)
    s = size
    cx, cy = s//2, s//2
    r = s//2 - 3
    # Circle representing a normal sphere
    d.ellipse([cx-r, cy-r, cx+r, cy+r], outline=TEAL2, width=1)
    # Gradient-style dots (NRM colors: red=right, green=up, blue=depth)
    d.ellipse([cx-r+2, cy-r+2, cx, cy], fill=(200,80,80,180))   # red quadrant
    d.ellipse([cx, cy-r+2, cx+r-2, cy], fill=(80,200,80,180))   # green quadrant
    d.ellipse([cx-r+2, cy, cx, cy+r-2], fill=(80,80,220,180))   # blue quadrant
    d.ellipse([cx, cy, cx+r-2, cy+r-2], fill=(200,200,80,180))  # yellow quadrant
    # Center dot
    glow_dot(d, cx, cy, WHITE, 1)
    return img

def icon_resources(size):
    img, d = new_icon(size)
    s = size
    # Database/stack of layers
    for i, (y, color) in enumerate([(3,TEAL),(7,TEAL2),(11,GOLD2),(15,GOLD)]):
        if y + 4 < s:
            d.ellipse([3, y, s-4, y+4], fill=color, outline=BG2)
    return img

def icon_twoda(size):
    img, d = new_icon(size)
    s = size
    # Grid table (2DA spreadsheet)
    cols, rows = 3, 4
    cw = (s-6) // cols
    rh = (s-6) // rows
    for c in range(cols):
        for r in range(rows):
            x1 = 3 + c*cw
            y1 = 3 + r*rh
            color = GOLD if (r==0 or c==0) else (TEAL2 if (r+c)%2==0 else BG2)
            d.rectangle([x1, y1, x1+cw-1, y1+rh-1], fill=color, outline=BORDER)
    return img

def icon_logo(size):
    img, d = new_icon(size)
    s = size
    cx, cy = s//2, s//2
    # Ghost icon: rounded head + body
    r = s//3
    # Head
    d.ellipse([cx-r, cy-r-2, cx+r, cy+1], fill=TEAL, outline=TEAL2)
    # Body (wavy bottom)
    body_pts = [
        cx-r, cy,
        cx-r, cy+r,
        cx-r+2, cy+r-1,
        cx-r+4, cy+r+1,
        cx, cy+r,
        cx+r-4, cy+r+1,
        cx+r-2, cy+r-1,
        cx+r, cy+r,
        cx+r, cy,
    ]
    # Convert flat to list of pairs
    bpts = [(body_pts[i], body_pts[i+1]) for i in range(0, len(body_pts), 2)]
    d.polygon(bpts, fill=TEAL, outline=TEAL2)
    # Eyes
    ey = cy - r//2 - 1
    glow_dot(d, cx-r//2+1, ey, GOLD, 2)
    glow_dot(d, cx+r//2-1, ey, GOLD, 2)
    return img

def icon_close(size):
    img, d = new_icon(size)
    s = size
    pad = 4
    # X mark
    d.line([(pad, pad), (s-pad, s-pad)], fill=RED, width=2)
    d.line([(s-pad, pad), (pad, s-pad)], fill=RED, width=2)
    return img

def icon_loadmodel(size):
    img, d = new_icon(size)
    s = size
    # Cube outline (3D model)
    cx, cy = s//2, s//2
    half = s//4
    # Top face
    top = [(cx, cy-half-2), (cx+half, cy-2), (cx, cy+half-4), (cx-half, cy-2)]
    d.polygon(top, outline=TEAL, fill=(68,204,255,60))
    # Right face
    right = [(cx+half, cy-2), (cx+half, cy+half), (cx, cy+half+half-2), (cx, cy+half-4)]
    d.polygon(right, outline=TEAL2, fill=(30,140,200,60))
    # Left face
    left = [(cx-half, cy-2), (cx, cy+half-4), (cx, cy+half+half-2), (cx-half, cy+half)]
    d.polygon(left, outline=GOLD2, fill=(200,160,30,60))
    return img

def icon_weightpaint(size):
    img, d = new_icon(size)
    s = size
    # Paintbrush + gradient orb
    # Brush handle
    d.line([(s-4, 3), (5, s-4)], fill=GOLD, width=2)
    # Brush tip
    d.polygon([(5,s-4),(3,s-3),(7,s-2)], fill=TEAL)
    # Heat-map circle (weight visualization)
    cx, cy = s//2+2, s//2-2
    r = s//4
    d.ellipse([cx-r, cy-r, cx+r, cy+r], fill=RED2, outline=RED)
    glow_dot(d, cx, cy, GOLD, 1)
    return img

def icon_cat_creature(size):
    img, d = new_icon(size)
    s = size
    cx, cy = s//2, s//2
    # Dragon/creature silhouette: body ellipse + head + tail
    # Body
    d.ellipse([4, cy-3, s-6, cy+4], fill=GREEN, outline=TEAL)
    # Head
    d.ellipse([s-8, cy-4, s-3, cy+3], fill=GREEN, outline=TEAL)
    # Snout
    d.polygon([(s-3,cy-1),(s-1,cy),(s-3,cy+1)], fill=TEAL)
    # Tail
    d.polygon([(4,cy-1),(2,cy-3),(3,cy+2)], fill=TEAL)
    # Legs
    for lx in [7, s-9]:
        d.line([(lx, cy+4),(lx-1, s-3)], fill=GREEN, width=2)
        d.line([(lx+3, cy+4),(lx+4, s-3)], fill=GREEN, width=2)
    return img

def icon_cat_character(size):
    img, d = new_icon(size)
    s = size
    cx = s//2
    # Head
    d.ellipse([cx-3, 2, cx+3, 8], fill=GOLD, outline=GOLD2)
    # Body
    d.polygon([(cx-4,8),(cx+4,8),(cx+5,s-4),(cx-5,s-4)], fill=TEAL, outline=TEAL2)
    # Arms
    d.line([(cx-4,10),(cx-7,s-6)], fill=TEAL, width=2)
    d.line([(cx+4,10),(cx+7,s-6)], fill=TEAL, width=2)
    # Legs
    d.line([(cx-2,s-4),(cx-3,s-2)], fill=TEAL, width=2)
    d.line([(cx+2,s-4),(cx+3,s-2)], fill=TEAL, width=2)
    return img

def icon_cat_item(size):
    img, d = new_icon(size)
    s = size
    # Sword / lightsaber
    # Blade
    d.polygon([(s//2-1, 3),(s//2+1, 3),(s//2+2, s-7),(s//2-2, s-7)], fill=TEAL, outline=WHITE)
    # Guard / crossguard
    d.rectangle([s//2-5, s-8, s//2+5, s-6], fill=GOLD, outline=GOLD2)
    # Handle
    d.rectangle([s//2-2, s-6, s//2+2, s-3], fill=GRAY, outline=BORDER)
    # Glow effect on blade
    glow_dot(d, s//2, 5, (180,220,255,180), 2)
    return img

def icon_cat_module(size):
    img, d = new_icon(size)
    s = size
    # Floor plan / map view
    # Outer walls
    d.rectangle([2, 2, s-3, s-3], outline=GOLD, width=1)
    # Inner room partition
    mid = s//2
    d.line([(mid, 2),(mid, s-4)], fill=GOLD2, width=1)
    d.line([(2, mid),(s-3, mid)], fill=GOLD2, width=1)
    # Door openings
    d.rectangle([mid-2, 2, mid+2, 3], fill=BG)   # top door
    d.rectangle([2, mid-2, 3, mid+2], fill=BG)   # left door
    # Small dot markers (waypoints)
    glow_dot(d, 5, 5, TEAL, 1)
    glow_dot(d, s-5, 5, TEAL, 1)
    glow_dot(d, mid+3, mid+3, GOLD, 1)
    return img

def icon_charbuilder(size):
    """Character Builder icon: body silhouette with skeleton overlay + head node."""
    img, d = new_icon(size)
    s = size
    cx = s // 2
    # Body outline (full figure)
    # Head circle (gold glow)
    d.ellipse([cx-3, 2, cx+3, 8], fill=GOLD, outline=GOLD2)
    # Spine (teal)
    d.line([(cx, 8), (cx, s-6)], fill=TEAL, width=2)
    # Shoulder bar
    d.line([(cx-5, 11), (cx+5, 11)], fill=GOLD2, width=2)
    # Hip bar
    d.line([(cx-4, s-8), (cx+4, s-8)], fill=GOLD2, width=2)
    # Arm bones
    d.line([(cx-5, 11), (cx-6, s-8)], fill=TEAL, width=1)
    d.line([(cx+5, 11), (cx+6, s-8)], fill=TEAL, width=1)
    # Leg bones
    d.line([(cx-2, s-8), (cx-3, s-2)], fill=TEAL, width=2)
    d.line([(cx+2, s-8), (cx+3, s-2)], fill=TEAL, width=2)
    # Skeleton joint dots (gold)
    for y in [11, s-8]:
        glow_dot(d, cx-5, y, GOLD, 1)
        glow_dot(d, cx+5, y, GOLD, 1)
    glow_dot(d, cx, s//2, TEAL, 1)
    return img


def icon_template(size):
    """Template icon: MDL file with skeleton lines."""
    img, d = new_icon(size)
    s = size
    # Document shape
    fx, fy = 3, 3
    fw, fh = s-7, s-6
    d.rectangle([fx, fy, fx+fw, fy+fh], fill=PANEL, outline=BORDER)
    # Folded corner
    d.polygon([(fx+fw-3,fy),(fx+fw,fy+3),(fx+fw-3,fy+3)], fill=BG2, outline=BORDER)
    # Skeleton lines inside doc
    cx = fx + fw//2
    # mini skeleton
    d.line([(cx, fy+3), (cx, fy+fh-2)], fill=TEAL, width=1)
    d.line([(cx-3, fy+5), (cx+3, fy+5)], fill=GOLD2, width=1)
    glow_dot(d, cx, fy+3, GOLD, 1)
    return img


def icon_selectall(size):
    """Select-all icon: dashed selection box with all nodes highlighted."""
    img, d = new_icon(size)
    s = size
    # Dashed selection rectangle
    for i in range(3, s-4, 3):
        d.point([(i, 3), (i, s-4)], fill=TEAL)
        d.point([(3, i), (s-4, i)], fill=TEAL)
    # Nodes inside (all gold = selected)
    positions = [(5,5),(s-6,5),(5,s-6),(s-6,s-6),(s//2,s//2)]
    for x, y in positions:
        glow_dot(d, x, y, GOLD, 2)
    return img


def icon_head(size):
    """Head/skull icon for head model slot."""
    img, d = new_icon(size)
    s = size
    cx, cy = s//2, s//2 - 1
    r = s//2 - 3
    # Skull shape
    d.ellipse([cx-r, cy-r, cx+r, cy+r//2], fill=GOLD2, outline=GOLD)
    # Jaw
    d.rectangle([cx-r+2, cy+r//2-1, cx+r-2, cy+r//2+3], fill=GOLD2, outline=GOLD)
    # Eye sockets
    d.ellipse([cx-r+3, cy-2, cx-1, cy+3], fill=BG)
    d.ellipse([cx+1, cy-2, cx+r-3, cy+3], fill=BG)
    # headhook dot (teal)
    glow_dot(d, cx, cy-r+1, TEAL, 1)
    return img


def icon_body(size):
    """Body model icon: torso silhouette with arms."""
    img, d = new_icon(size)
    s = size
    cx = s//2
    # Torso box
    d.rectangle([cx-4, 4, cx+4, s-6], fill=TEAL2, outline=TEAL)
    # Arms
    d.rectangle([cx-7, 5, cx-5, s//2+2], fill=GOLD2, outline=GOLD2)
    d.rectangle([cx+5, 5, cx+7, s//2+2], fill=GOLD2, outline=GOLD2)
    # Legs
    d.rectangle([cx-4, s-6, cx-1, s-2], fill=GOLD2, outline=GOLD2)
    d.rectangle([cx+1, s-6, cx+4, s-2], fill=GOLD2, outline=GOLD2)
    # headhook attachment point (teal dot at top)
    glow_dot(d, cx, 3, TEAL, 1)
    return img


def icon_cat_other(size):
    img, d = new_icon(size)
    s = size
    cx, cy = s//2, s//2
    # Star / asterisk shape
    for angle in range(0, 180, 36):
        rad = math.radians(angle)
        r = s//2 - 3
        x1 = int(cx + r*math.cos(rad))
        y1 = int(cy + r*math.sin(rad))
        x2 = int(cx - r*math.cos(rad))
        y2 = int(cy - r*math.sin(rad))
        d.line([(x1,y1),(x2,y2)], fill=PURPLE, width=1)
    glow_dot(d, cx, cy, GOLD, 2)
    return img

# ═══════════════════════════════════════════════════════════════════════════════
# Icon registry & generation
# ═══════════════════════════════════════════════════════════════════════════════

ICON_FUNCS = {
    "open":          icon_open,
    "autorig":       icon_autorig,
    "export":        icon_export,
    "import":        icon_import,
    "settings":      icon_settings,
    "refresh":       icon_refresh,
    "cloth":         icon_cloth,
    "modular":       icon_modular,
    "diag":          icon_diag,
    "texture":       icon_texture,
    "library":       icon_library,
    "search":        icon_search,
    "skeleton":      icon_skeleton,
    "props":         icon_props,
    "anims":         icon_anims,
    "rig":           icon_rig,
    "normalmap":     icon_normalmap,
    "resources":     icon_resources,
    "twoda":         icon_twoda,
    "logo":          icon_logo,
    "close":         icon_close,
    "loadmodel":     icon_loadmodel,
    "weightpaint":   icon_weightpaint,
    "cat_creature":  icon_cat_creature,
    "cat_character": icon_cat_character,
    "cat_item":      icon_cat_item,
    "cat_module":    icon_cat_module,
    "cat_other":     icon_cat_other,
    # New Character Builder icons
    "charbuilder":   icon_charbuilder,
    "template":      icon_template,
    "selectall":     icon_selectall,
    "head":          icon_head,
    "body":          icon_body,
}

generated = 0
for name, fn in ICON_FUNCS.items():
    for size in [16, 24]:
        try:
            img = fn(size)
            save(img, name, size)
            generated += 1
        except Exception as e:
            print(f"  ERROR {name}_{size}: {e}")

print(f"Generated {generated} icons in {OUT_DIR}/")
