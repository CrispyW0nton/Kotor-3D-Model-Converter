"""
Phase 19 UI Render — KotOR-style icon system
Generates render_check/ghostrigger_phase19_ui.png at 1400×860
Shows the full GhostRigger UI with KotOR pixel-art icons replacing all emojis.
"""
from PIL import Image, ImageDraw, ImageFont
import os, math

W, H = 1400, 860
OUT  = "render_check/ghostrigger_phase19_ui.png"
os.makedirs("render_check", exist_ok=True)

# ── Palette (matches the app) ─────────────────────────────────────────────────
BG      = (13,  13,  26)
BG2     = (18,  18,  38)
PANEL   = (26,  26,  56)
PANEL2  = (22,  22,  50)
BORDER  = (42,  42,  90)
ACCENT  = (58,  58, 255)
ACCENT2 = (106, 106, 255)
GOLD    = (255, 204,  68)
GOLD2   = (230, 170,  30)
TEAL    = ( 68, 204, 255)
TEAL2   = ( 30, 140, 200)
GREEN   = ( 68, 255, 136)
RED     = (255,  68,  68)
WHITE   = (224, 224, 255)
GRAY    = (144, 144, 200)
PURPLE  = (160,  80, 255)
SEP     = (37,  37,  80)
ORANGE  = (255, 136,  68)

img = Image.new("RGB", (W, H), BG)
d   = ImageDraw.Draw(img)

# ── Font helpers ──────────────────────────────────────────────────────────────
def font(size=10, bold=False):
    try:
        name = "DejaVuSans-Bold.ttf" if bold else "DejaVuSans.ttf"
        return ImageFont.truetype(f"/usr/share/fonts/truetype/dejavu/{name}", size)
    except:
        return ImageFont.load_default()

def text(x, y, txt, color=WHITE, size=10, bold=False):
    d.text((x, y), txt, fill=color, font=font(size, bold))

def rect(x1, y1, x2, y2, fill=PANEL, outline=BORDER):
    d.rectangle([x1, y1, x2, y2], fill=fill, outline=outline)

def hline(y, x1=0, x2=W, color=SEP):
    d.line([(x1,y),(x2,y)], fill=color, width=1)

def vline(x, y1=0, y2=H, color=SEP):
    d.line([(x,y1),(x,y2)], fill=color, width=1)

# ── Load icon helper ──────────────────────────────────────────────────────────
ICON_DIR = "src/gui/icons"
_icon_cache = {}
def load_icon(name, size=16):
    key = (name, size)
    if key not in _icon_cache:
        p = os.path.join(ICON_DIR, f"{name}_{size}.png")
        if os.path.exists(p):
            ico = Image.open(p).convert("RGBA")
            _icon_cache[key] = ico
        else:
            _icon_cache[key] = None
    return _icon_cache[key]

def paste_icon(x, y, name, size=16):
    ico = load_icon(name, size)
    if ico:
        img.paste(ico, (x, y), ico)

# ─────────────────────────────────────────────────────────────────────────────
# LAYOUT CONSTANTS
# ─────────────────────────────────────────────────────────────────────────────
HDR_H     = 38
TOOLBAR_H = 36
STATUS_H  = 22
CONTENT_Y = HDR_H + TOOLBAR_H
CONTENT_H = H - HDR_H - TOOLBAR_H - STATUS_H
LEFT_W    = 230
RIGHT_W   = 260
CENTER_X  = LEFT_W
CENTER_W  = W - LEFT_W - RIGHT_W
LOG_H     = 90

# ═══════════════════════════════════════════════════════════════════════════════
# 1. HEADER
# ═══════════════════════════════════════════════════════════════════════════════
rect(0, 0, W, HDR_H, fill=BG2, outline=BORDER)
paste_icon(8, 8, "logo", 24)
text(38, 5,  "GhostRigger-K1-K2", color=WHITE, size=13, bold=True)
text(38, 22, "Odyssey Engine Pipeline  │  KotOR 1 & 2 TSL", color=GRAY, size=9)

# Right side: version badge
vbx = W - 200
rect(vbx, 8, W-8, 30, fill=ACCENT, outline=ACCENT2)
text(vbx+8, 12, "v5.5  ✦  4372 tests", color=WHITE, size=9, bold=True)

# IPC status dot
d.ellipse([vbx-18, 14, vbx-10, 22], fill=GREEN, outline=(30,180,80))
text(vbx-60, 14, "IPC Ready", color=GRAY, size=8)

hline(HDR_H, color=BORDER)

# ═══════════════════════════════════════════════════════════════════════════════
# 2. TOOLBAR
# ═══════════════════════════════════════════════════════════════════════════════
TY = HDR_H
rect(0, TY, W, TY+TOOLBAR_H, fill=PANEL2, outline=SEP)

# Model name pill
rect(8, TY+5, 230, TY+31, fill=BG, outline=TEAL)
paste_icon(12, TY+8, "loadmodel", 16)
text(32, TY+10, "c_deadeye.mdl  │  K1  │  42 mesh  │  8 anim", color=TEAL, size=8)

# Toolbar buttons with icons
toolbar_btns = [
    ("open",        "Open",     ACCENT),
    ("import",      "Import",   PANEL),
    ("export",      "Export",   PANEL),
    ("autorig",     "Auto-Rig", PANEL),
    ("cloth",       "Cloth",    PANEL),
    ("modular",     "Modular",  PANEL),
    ("diag",        "Diag",     PANEL),
    ("settings",    "Settings", PANEL),
]
tbx = 240
for icon_name, label, bg in toolbar_btns:
    bw = 72
    rect(tbx, TY+4, tbx+bw, TY+32, fill=bg, outline=BORDER)
    paste_icon(tbx+6, TY+8, icon_name, 16)
    text(tbx+26, TY+11, label, color=WHITE, size=8)
    tbx += bw + 4

# Keyboard shortcut hint
text(tbx+6, TY+12, "Ctrl+O / Ctrl+I / Ctrl+E  │  R  │  F  │  Ctrl+D  │  F2", color=GRAY, size=7)

hline(TY+TOOLBAR_H, color=BORDER)

# ═══════════════════════════════════════════════════════════════════════════════
# 3. LEFT PANEL (Library)
# ═══════════════════════════════════════════════════════════════════════════════
rect(0, CONTENT_Y, LEFT_W, H-STATUS_H, fill=PANEL2, outline=SEP)
vline(LEFT_W, CONTENT_Y, H-STATUS_H, color=BORDER)

LY = CONTENT_Y + 4

# Library heading
paste_icon(6, LY+2, "library", 16)
text(26, LY+4, "Game Library", color=GOLD, size=10, bold=True)
LY += 22

# Game dir buttons
for lbl, bg in [("Set K1 Dir",PANEL),("Set K2 Dir",PANEL),("Auto-detect",PANEL)]:
    bw = LEFT_W//3 - 4
    rect(4, LY, 4+bw, LY+16, fill=bg, outline=BORDER)
    text(7, LY+3, lbl, color=WHITE, size=7)
    LY2 = LY  # keep same row for scan buttons
    
# Scan on right
rect(LEFT_W-68, LY-14, LEFT_W-4, LY, fill=ACCENT, outline=ACCENT2)
text(LEFT_W-62, LY-12, "Scan", color=WHITE, size=7, bold=True)
LY += 6

# Game filter radio
text(6, LY+2, "Filter:", color=GRAY, size=8)
for i, (lbl, col) in enumerate([("All",WHITE),("K1",TEAL),("K2",GREEN)]):
    d.ellipse([45+i*30, LY+4, 52+i*30, LY+11], fill=col if i==0 else GRAY, outline=col)
    text(55+i*30, LY+2, lbl, color=col, size=8)
LY += 18

# Category tabs with KotOR icons
CAT_TABS = [
    ("library",       "All"),
    ("cat_creature",  "Cre"),
    ("cat_character", "Chr"),
    ("cat_item",      "Itm"),
    ("cat_module",    "Mod"),
    ("cat_other",     "Oth"),
]
tab_w = (LEFT_W - 4) // len(CAT_TABS)
for i, (icon_name, label) in enumerate(CAT_TABS):
    tx = 2 + i * tab_w
    is_active = (i == 0)
    tab_bg = ACCENT if is_active else PANEL
    tab_fg = WHITE if is_active else GRAY
    rect(tx, LY, tx+tab_w-1, LY+18, fill=tab_bg, outline=BORDER)
    paste_icon(tx+2, LY+1, icon_name, 16)
    text(tx+19, LY+4, label, color=tab_fg, size=7)
LY += 20

# Search bar
rect(4, LY, LEFT_W-4, LY+16, fill=BG, outline=TEAL)
paste_icon(6, LY+1, "search", 16)
text(24, LY+3, "Search models…", color=GRAY, size=8)
LY += 20

# Model list
list_entries = [
    ("K1", "c_deadeye",     "Cre", TEAL),
    ("K1", "c_darkmast",    "Cre", TEAL),
    ("K1", "n_twilek001",   "Chr", (136,170,255)),
    ("K2", "c_holophi001",  "Cre", GREEN),
    ("K1", "w_blste_001",   "Itm", (255,170,136)),
    ("K1", "m01aa",         "Mod", GOLD),
    ("K2", "003ebo",        "Mod", GREEN),
    ("K1", "n_ithorian",    "Chr", (136,170,255)),
    ("K1", "c_hutt",        "Cre", TEAL),
    ("K2", "w_lghtsbr_004", "Itm", (255,170,136)),
    ("K2", "n_mandal001",   "Chr", GREEN),
    ("K1", "p_hk47",        "Cre", TEAL),
]
cat_icon_map = {"Cre":"cat_creature","Chr":"cat_character","Itm":"cat_item","Mod":"cat_module"}
for entry in list_entries:
    if LY > H - STATUS_H - LOG_H - 80:
        break
    game, resref, cat, col = entry
    # Alternating row bg
    row_bg = BG if list_entries.index(entry) % 2 == 0 else PANEL2
    rect(4, LY, LEFT_W-4, LY+14, fill=row_bg, outline=SEP)
    ico = cat_icon_map.get(cat, "cat_other")
    paste_icon(6, LY, ico, 14)
    text(22, LY+1, f"[{game}]", color=GOLD2 if game=="K1" else GREEN, size=7)
    text(50, LY+1, resref, color=col, size=7)
    LY += 15

# Load + Extract buttons
LY += 4
rect(4, LY, LEFT_W//2-4, LY+18, fill=ACCENT, outline=ACCENT2)
paste_icon(8, LY+1, "loadmodel", 16)
text(28, LY+4, "Load Model", color=WHITE, size=8, bold=True)
rect(LEFT_W//2+2, LY, LEFT_W-4, LY+18, fill=PANEL, outline=BORDER)
paste_icon(LEFT_W//2+5, LY+1, "open", 16)
text(LEFT_W//2+24, LY+4, "Extract", color=TEAL, size=8)

# ═══════════════════════════════════════════════════════════════════════════════
# 4. CENTER — VIEWPORT
# ═══════════════════════════════════════════════════════════════════════════════
VX, VY = LEFT_W+1, CONTENT_Y
VW = W - LEFT_W - RIGHT_W - 2
VH = CONTENT_H - LOG_H

rect(VX, VY, VX+VW, VY+VH, fill=BG, outline=BORDER)

# Grid
for gx in range(0, VW, 30):
    d.line([(VX+gx, VY+1),(VX+gx, VY+VH-1)], fill=(20,20,45), width=1)
for gy in range(0, VH, 30):
    d.line([(VX+1, VY+gy),(VX+VW-1, VY+gy)], fill=(20,20,45), width=1)

# Origin axes
mcx = VX + VW//2
mcy = VY + VH//2
d.line([(mcx-80,mcy),(mcx+80,mcy)], fill=(60,60,120), width=1)
d.line([(mcx,mcy-80),(mcx,mcy+80)], fill=(60,60,120), width=1)

# Character silhouette
def humanoid(cx, cy, scale=1.0):
    sc = scale
    # Head
    r = int(14*sc)
    d.ellipse([cx-r, cy-int(70*sc), cx+r, cy-int(42*sc)], 
              outline=TEAL, fill=(13,13,26), width=2)
    # Body
    d.polygon([
        (cx-int(16*sc), cy-int(42*sc)),
        (cx+int(16*sc), cy-int(42*sc)),
        (cx+int(12*sc), cy+int(10*sc)),
        (cx-int(12*sc), cy+int(10*sc)),
    ], outline=TEAL, fill=(13,13,26))
    # Arms
    d.line([(cx-int(16*sc),cy-int(35*sc)),(cx-int(28*sc),cy+int(5*sc))], fill=TEAL, width=2)
    d.line([(cx+int(16*sc),cy-int(35*sc)),(cx+int(28*sc),cy+int(5*sc))], fill=TEAL, width=2)
    # Legs
    d.line([(cx-int(8*sc),cy+int(10*sc)),(cx-int(10*sc),cy+int(50*sc))], fill=TEAL, width=2)
    d.line([(cx+int(8*sc),cy+int(10*sc)),(cx+int(10*sc),cy+int(50*sc))], fill=TEAL, width=2)
    # Bone joints
    for bx,by in [(cx, cy-int(56*sc)),(cx, cy-int(10*sc)),
                  (cx-int(22*sc),cy),(cx+int(22*sc),cy),
                  (cx-int(10*sc),cy+int(50*sc)),(cx+int(10*sc),cy+int(50*sc))]:
        d.ellipse([bx-3,by-3,bx+3,by+3], fill=GOLD, outline=GOLD2)

humanoid(mcx, mcy)

# Walkmesh overlay (green = walkable, red = blocked)
wm_polys_green = [
    [(mcx-80,mcy+52),(mcx+80,mcy+52),(mcx+70,mcy+82),(mcx-70,mcy+82)],
    [(mcx+80,mcy+52),(mcx+130,mcy+72),(mcx+120,mcy+92),(mcx+70,mcy+82)],
    [(mcx-80,mcy+52),(mcx-130,mcy+72),(mcx-120,mcy+92),(mcx-70,mcy+82)],
]
wm_polys_red = [
    [(mcx+130,mcy+72),(mcx+160,mcy+82),(mcx+150,mcy+102),(mcx+120,mcy+92)],
]
for poly in wm_polys_green:
    d.polygon(poly, fill=(20,60,20,120), outline=(40,180,40))
for poly in wm_polys_red:
    d.polygon(poly, fill=(60,15,15,120), outline=(180,40,40))

# Bone overlay (skeleton lines)
joints = {
    "head":   (mcx, mcy-56),
    "neck":   (mcx, mcy-42),
    "chest":  (mcx, mcy-20),
    "hips":   (mcx, mcy+10),
    "l_sho":  (mcx-16, mcy-35),
    "r_sho":  (mcx+16, mcy-35),
    "l_hand": (mcx-28, mcy+5),
    "r_hand": (mcx+28, mcy+5),
    "l_knee": (mcx-10, mcy+30),
    "r_knee": (mcx+10, mcy+30),
    "l_foot": (mcx-10, mcy+50),
    "r_foot": (mcx+10, mcy+50),
}
bone_pairs = [
    ("head","neck"),("neck","chest"),("chest","hips"),
    ("chest","l_sho"),("l_sho","l_hand"),
    ("chest","r_sho"),("r_sho","r_hand"),
    ("hips","l_knee"),("l_knee","l_foot"),
    ("hips","r_knee"),("r_knee","r_foot"),
]
for a, b in bone_pairs:
    if a in joints and b in joints:
        d.line([joints[a], joints[b]], fill=(80,255,160,180), width=1)
for name, (jx,jy) in joints.items():
    d.ellipse([jx-2,jy-2,jx+2,jy+2], fill=GREEN, outline=(30,180,80))

# Viewport HUD (top-left)
hud_bg = (10,10,25,220)
# Model name badge
rect(VX+6, VY+6, VX+200, VY+20, fill=BG2, outline=TEAL)
paste_icon(VX+8, VY+3, "loadmodel", 16)
text(VX+28, VY+8, "c_deadeye.mdl  |  K1", color=TEAL, size=8)

# Right HUD badges
badge_x = VX + VW - 6
for label, col in [
    ("K1",       GOLD),
    ("42 mesh",  TEAL),
    ("textured", GREEN),
    ("60 fps",   GREEN),
    ("CPU",      GRAY),
    ("solid",    GRAY),
]:
    bw = len(label)*6 + 10
    badge_x -= bw + 3
    rect(badge_x, VY+6, badge_x+bw, VY+18, fill=BG2, outline=col)
    text(badge_x+4, VY+8, label, color=col, size=7)

# Axis gizmo (bottom-right)
gx, gy = VX+VW-40, VY+VH-40
d.line([(gx,gy),(gx+22,gy)],    fill=(255,80,80),  width=2)  # X axis
d.line([(gx,gy),(gx,gy-22)],    fill=(80,255,80),  width=2)  # Y axis
d.line([(gx,gy),(gx-12,gy+12)], fill=(80,80,255),  width=2)  # Z axis
text(gx+24, gy-4, "X", color=(255,80,80), size=8)
text(gx-2, gy-28, "Y", color=(80,255,80), size=8)
text(gx-24, gy+14, "Z", color=(80,80,255), size=8)

# Camera info (bottom-left of viewport)
text(VX+6, VY+VH-18, "Perspective  |  dist: 8.5  |  ortho: OFF  |  W: walkmesh ON", color=GRAY, size=7)

# ═══════════════════════════════════════════════════════════════════════════════
# 5. LOG PANEL
# ═══════════════════════════════════════════════════════════════════════════════
LGY = CONTENT_Y + CONTENT_H - LOG_H
rect(VX, LGY, VX+VW, LGY+LOG_H, fill=BG2, outline=BORDER)
hline(LGY, VX, VX+VW, color=BORDER)

# Log header
rect(VX, LGY, VX+VW, LGY+16, fill=PANEL, outline=SEP)
text(VX+6, LGY+3, "Log  (Ctrl+`)  ▼", color=GOLD, size=8, bold=True)
text(VX+VW-100, LGY+3, "Copy  Clear  Save", color=GRAY, size=7)

log_msgs = [
    ("[+] Loaded c_deadeye.mdl — 42 mesh nodes, 8 animations, 6 bone slots", GREEN),
    ("[+] ResourceManager: BIF lookup in 1.2 ms (primary)", TEAL),
    ("[i] Walkmesh overlay: 3 walkable polys, 1 blocked", TEAL),
    ("[i] Skeleton: 12 joints, LBS weights OK (max 4 infl/vert)", GOLD),
    ("[*] Phase 19: KotOR icon system active — 56 icons loaded", WHITE),
]
ly = LGY + 19
for msg, col in log_msgs:
    if ly >= LGY + LOG_H - 4:
        break
    text(VX+6, ly, msg, color=col, size=7)
    ly += 13

# ═══════════════════════════════════════════════════════════════════════════════
# 6. RIGHT PANEL (Props / Rig / Textures / etc.)
# ═══════════════════════════════════════════════════════════════════════════════
RX = W - RIGHT_W
rect(RX, CONTENT_Y, W, H-STATUS_H, fill=PANEL2, outline=SEP)
vline(RX, CONTENT_Y, H-STATUS_H, color=BORDER)

RY = CONTENT_Y + 4

# Right panel tabs with icons
right_tabs = [
    ("props",     "Props"),
    ("skeleton",  "Rig"),
    ("cloth",     "Cloth"),
    ("texture",   "Tex"),
    ("normalmap", "Norm"),
    ("diag",      "Diag"),
    ("anims",     "Anim"),
]
tab_w2 = (RIGHT_W - 4) // len(right_tabs)
for i, (ico, lbl) in enumerate(right_tabs):
    tx = RX + 2 + i*tab_w2
    is_active = (i == 0)
    rect(tx, RY, tx+tab_w2-1, RY+17, fill=ACCENT if is_active else PANEL, outline=BORDER)
    paste_icon(tx+2, RY+1, ico, 16)
    text(tx+19, RY+4, lbl, color=WHITE if is_active else GRAY, size=6)
RY += 20

# Props content
text(RX+6, RY+2, "Properties", color=GOLD, size=9, bold=True)
RY += 16

props_items = [
    ("Model", "c_deadeye"),
    ("Game",  "KotOR 1"),
    ("Super", "c_deadeye"),
    ("Type",  "character"),
    ("Nodes", "42 mesh, 6 bone"),
    ("Verts", "8,432"),
    ("Faces", "14,218"),
    ("Tex",   "c_deadeye_01, 02"),
    ("Anims", "8 clips"),
]
for k, v in props_items:
    rect(RX+4, RY, RX+RIGHT_W-4, RY+13, fill=BG, outline=SEP)
    text(RX+8,  RY+2, k+":", color=GRAY, size=7)
    text(RX+55, RY+2, v,     color=TEAL, size=7)
    RY += 14

# Skeleton tree section
RY += 4
text(RX+6, RY+2, "Skeleton  /  Nodes", color=GOLD, size=8, bold=True)
paste_icon(RX+RIGHT_W-22, RY+1, "skeleton", 16)
RY += 16

skeleton_nodes = [
    (0, "c_deadeye",      "dummy",  ""),
    (1, "  + deadeye_g0", "skin",   "8,432v"),
    (1, "  + head",       "trimesh","980v"),
    (1, "  + larm_g0",    "skin",   "1,240v"),
    (1, "  + rarm_g0",    "skin",   "1,100v"),
    (2, "    + lhand",    "dummy",  ""),
    (2, "    + rhand",    "dummy",  ""),
    (1, "  [walkmesh]",   "aabb",   ""),
]
node_colors = {
    "dummy": GRAY, "skin": GREEN, "trimesh": TEAL, "aabb": ORANGE
}
for _, name, ntype, extra in skeleton_nodes:
    nc = node_colors.get(ntype, WHITE)
    rect(RX+4, RY, RX+RIGHT_W-4, RY+13, fill=BG2, outline=SEP)
    text(RX+8,  RY+2, name,  color=nc, size=7)
    text(RX+RIGHT_W-45, RY+2, ntype, color=(80,80,120), size=6)
    if extra:
        text(RX+RIGHT_W-75, RY+2, extra, color=GRAY, size=6)
    RY += 14

# Transform section
RY += 4
rect(RX+4, RY, RX+RIGHT_W-4, RY+14, fill=PANEL, outline=GOLD2)
text(RX+8, RY+3, "Node Transform (editable)", color=GOLD2, size=7)
RY += 16
for lbl, val in [("X", "0.000"), ("Y", "0.000"), ("Z", "1.842")]:
    rect(RX+4+(["X","Y","Z"].index(lbl))*(RIGHT_W//3-2), RY,
         RX+4+(["X","Y","Z"].index(lbl)+1)*(RIGHT_W//3-2)-2, RY+14,
         fill=BG, outline=TEAL2)
    text(RX+8+(["X","Y","Z"].index(lbl))*(RIGHT_W//3-2), RY+3,
         f"{lbl}: {val}", color=TEAL, size=7)
RY += 18

# 2DA/GFF Preview
rect(RX+4, RY, RX+RIGHT_W-4, RY+14, fill=PANEL, outline=TEAL)
paste_icon(RX+6, RY, "twoda", 16)
text(RX+24, RY+3, "2DA / GFF Preview", color=TEAL, size=7, bold=True)
RY += 16
preview_rows = [
    ("label",  "appearance",  "TEAL"),
    ("0",      "NONE",        "GRAY"),
    ("1",      "S_Male01",    "WHITE"),
    ("2",      "S_Female01",  "WHITE"),
    ("3",      "N_DrdT3H4",   "WHITE"),
]
for k, v, _ in preview_rows:
    rect(RX+4, RY, RX+RIGHT_W-4, RY+11, fill=BG, outline=SEP)
    text(RX+8,  RY+1, k, color=GOLD2, size=6)
    text(RX+35, RY+1, v, color=TEAL,  size=6)
    RY += 12

# ═══════════════════════════════════════════════════════════════════════════════
# 7. STATUS BAR
# ═══════════════════════════════════════════════════════════════════════════════
SY = H - STATUS_H
rect(0, SY, W, H, fill=BG2, outline=BORDER)
hline(SY, color=BORDER)

status_fields = [
    (f"4372 tests  11 skipped", GREEN),
    ("c_deadeye.mdl", TEAL),
    ("K1  /  Creature", GOLD),
    ("CPU Renderer", GRAY),
    ("Rigged: LBS x6", TEAL),
    ("Phase 19  –  KotOR Icons", ACCENT2),
    ("v5.5  2026-04-03", WHITE),
]
sx = 8
for lbl, col in status_fields:
    text(sx, SY+4, lbl, color=col, size=8)
    sx += len(lbl)*6 + 20
    if sx < W - 10:
        d.line([(sx-12, SY+5),(sx-12, SY+16)], fill=SEP, width=1)

# ═══════════════════════════════════════════════════════════════════════════════
# 8. ANNOTATION CALLOUTS (Phase 19 features)
# ═══════════════════════════════════════════════════════════════════════════════
ann_y = CONTENT_Y + 8
ann_items = [
    (LEFT_W + 10,    "KotOR Icons in Category Tabs",         GOLD),
    (LEFT_W + 10,    "Icons replace all emoji buttons",       TEAL),
    (VX + VW//2 - 80,"Walkmesh overlay (green/red polys)",   GREEN),
    (VX + VW - 240,  "Bone overlay (joints + chain)",        (68,255,136)),
]
for ix, label, col in ann_items:
    if ann_y > CONTENT_Y + VH - 20:
        break
    # Small callout box
    bw = len(label)*5 + 14
    if ix + bw < VX + VW:
        rect(ix, ann_y, ix+bw, ann_y+13, fill=(20,20,50,200), outline=col)
        text(ix+5, ann_y+2, label, color=col, size=7)
        ann_y += 17

# ═══════════════════════════════════════════════════════════════════════════════
# 9. PHASE 19 BADGE
# ═══════════════════════════════════════════════════════════════════════════════
# Bottom-right corner badge
bx, by = W - 280, H - STATUS_H - 26
rect(bx, by, W - 8, by+20, fill=ACCENT, outline=ACCENT2)
paste_icon(bx+6, by+2, "logo", 16)
text(bx+26, by+4, "Phase 19  –  KotOR-style icon system  –  56 icons", color=WHITE, size=8, bold=True)

# ═══════════════════════════════════════════════════════════════════════════════
# SAVE
# ═══════════════════════════════════════════════════════════════════════════════
img.save(OUT)
print(f"Saved {OUT}  ({W}×{H})")
