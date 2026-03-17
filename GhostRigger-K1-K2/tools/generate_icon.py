#!/usr/bin/env python3
"""
GhostRigger Icon Generator
Generates the ghostrigger.ico (multi-size Windows icon) + ghostrigger_icon.png
from a source PNG. If no source is supplied, builds a procedural icon.

Usage:
    python tools/generate_icon.py                         # procedural icon
    python tools/generate_icon.py path/to/source.png      # from custom source
"""

import sys, os, math, random
from pathlib import Path

try:
    from PIL import Image, ImageDraw, ImageFilter
    import numpy as np
except ImportError:
    print("ERROR: Pillow and numpy required – run: pip install Pillow numpy")
    sys.exit(1)

# ── Paths ─────────────────────────────────────────────────────────────────────
REPO_ROOT = Path(__file__).resolve().parent.parent
ICON_DIR  = REPO_ROOT / "assets" / "icons"
ICON_DIR.mkdir(parents=True, exist_ok=True)

ICO_SIZES = [256, 128, 64, 48, 32, 16]


def remove_white_border(arr: np.ndarray) -> np.ndarray:
    """Replace near-white pixels with dark background (removes watermark borders)."""
    white_mask = (arr[:,:,0] > 200) & (arr[:,:,1] > 200) & (arr[:,:,2] > 200)
    arr = arr.copy()
    arr[white_mask] = [0, 5, 2, 255]
    return arr


def boost_greens(arr: np.ndarray) -> np.ndarray:
    """Boost the green channel where it dominates (neon eyes / matrix elements)."""
    arr = arr.astype(np.float32)
    g_mask = (arr[:,:,1] > arr[:,:,0]) & (arr[:,:,1] > arr[:,:,2]) & (arr[:,:,1] > 20)
    arr[g_mask, 1] = np.clip(arr[g_mask, 1] * 1.35, 0, 255)
    arr[g_mask, 0] = np.clip(arr[g_mask, 0] * 0.75, 0, 255)
    arr[g_mask, 2] = np.clip(arr[g_mask, 2] * 0.85, 0, 255)
    return arr.astype(np.uint8)


def add_eye_glow(img: Image.Image) -> Image.Image:
    """Auto-detect bright green cluster (eyes) and add glow effect."""
    SIZE = img.width
    arr = np.array(img)
    bright = (arr[:,:,1] > 150) & (arr[:,:,1] > arr[:,:,0]*2) & (arr[:,:,1] > arr[:,:,2]*2)
    coords = np.where(bright)
    if len(coords[0]) > 10:
        ey = int(coords[0].mean())
        ex = int(coords[1].mean())
        glow = Image.new('RGBA', (SIZE, SIZE), (0,0,0,0))
        gd = ImageDraw.Draw(glow)
        for r, g, a in [(80,200,100),(50,180,150),(30,220,200),(15,255,255)]:
            gd.ellipse([ex-r, ey-r, ex+r, ey+r], fill=(0,g,10,a))
        glow_b = glow.filter(ImageFilter.GaussianBlur(radius=20))
        img = Image.alpha_composite(img, glow_b)
    return img


def apply_rounded_mask(img: Image.Image, radius_frac: float = 0.12) -> Image.Image:
    """Apply a rounded-square transparency mask."""
    SIZE = img.width
    mask = Image.new('L', (SIZE, SIZE), 0)
    md = ImageDraw.Draw(mask)
    r = int(SIZE * radius_frac)
    md.rounded_rectangle([0, 0, SIZE-1, SIZE-1], radius=r, fill=255)
    img = img.copy()
    img.putalpha(mask)
    return img


def build_from_source(source_path: str) -> Image.Image:
    """Process an existing custom source PNG."""
    src = Image.open(source_path).convert('RGBA')
    arr = np.array(src)
    arr = remove_white_border(arr)
    arr = boost_greens(arr)
    img = Image.fromarray(arr)
    img = add_eye_glow(img)
    img = apply_rounded_mask(img)
    return img


def build_procedural(size: int = 1024) -> Image.Image:
    """Build a procedural hooded-figure icon when no source image is available."""
    S = size
    img = Image.new('RGBA', (S, S), (0, 0, 0, 255))

    # -- Subtle background radial gradient
    arr = np.zeros((S, S, 4), dtype=np.float32)
    arr[:,:,3] = 255
    cx, cy = S//2, S//2
    ys, xs = np.mgrid[0:S, 0:S]
    dist = np.sqrt((xs-cx)**2 + (ys-cy)**2) / (S * 0.7)
    arr[:,:,1] = np.clip(dist * 15, 0, 20)
    img = Image.fromarray(arr.astype(np.uint8))
    draw = ImageDraw.Draw(img)

    # -- Matrix rain
    random.seed(42)
    for col_x in range(0, S, max(1, S//36)):
        h = random.randint(S//13, S//3)
        y0 = random.randint(0, S - h)
        for i in range(h // max(1, S//64)):
            char_y = y0 + i * max(1, S//64)
            if char_y < S:
                g = max(20, 80 - i*4)
                a = max(0, 80 - i*3)
                draw.rectangle([col_x, char_y, col_x + max(1,S//100), char_y + max(1,S//85)],
                               fill=(0, g, 0, a))

    # -- Hood silhouette
    hcx, hcy = S//2, int(S*0.38)
    hood = [(hcx - int(S*.32), int(S*.80)),
            (hcx - int(S*.28), int(S*.20)),
            (hcx - int(S*.18), int(S*.05)),
            (hcx,              int(S*.02)),
            (hcx + int(S*.18), int(S*.05)),
            (hcx + int(S*.28), int(S*.20)),
            (hcx + int(S*.32), int(S*.80))]
    draw.polygon(hood, fill=(6, 8, 7))
    shadow = [(hcx - int(S*.18), int(S*.18)),
              (hcx - int(S*.22), int(S*.50)),
              (hcx,              int(S*.56)),
              (hcx + int(S*.22), int(S*.50)),
              (hcx + int(S*.18), int(S*.18))]
    draw.polygon(shadow, fill=(2, 4, 3))

    # -- Glowing eyes
    eye_y  = int(S * 0.36)
    eye_sep = int(S * 0.11)
    eye_r  = int(S * 0.03)
    for ex in [hcx - eye_sep, hcx + eye_sep]:
        for r_m, g, a in [(3.5,80,25),(2.5,130,50),(1.8,180,90),(1.2,220,160),(0.8,255,220),(0.5,255,255)]:
            r = int(eye_r * r_m)
            draw.ellipse([ex-r, eye_y-r, ex+r, eye_y+r], fill=(0, g, 10, a))
        rc = int(eye_r * 0.4)
        draw.ellipse([ex-rc, eye_y-rc, ex+rc, eye_y+rc], fill=(180,255,150,255))

    # -- Hood edge glow
    for t, g, a in [(8, 60, 40), (4, 100, 80), (2, 160, 130)]:
        draw.line(hood, fill=(0, g, 10, a), width=t)

    # -- Eye glow layers (blurred)
    glow  = Image.new('RGBA', (S, S), (0,0,0,0))
    gd    = ImageDraw.Draw(glow)
    for ex in [hcx - eye_sep, hcx + eye_sep]:
        r = eye_r * 2
        gd.ellipse([ex-r, eye_y-r, ex+r, eye_y+r], fill=(0,200,30,120))
    img = Image.alpha_composite(img, glow.filter(ImageFilter.GaussianBlur(30)))

    glow2 = Image.new('RGBA', (S, S), (0,0,0,0))
    gd2   = ImageDraw.Draw(glow2)
    for ex in [hcx - eye_sep, hcx + eye_sep]:
        r = eye_r * 5
        gd2.ellipse([ex-r, eye_y-r, ex+r, eye_y+r], fill=(0,120,20,60))
    img = Image.alpha_composite(img, glow2.filter(ImageFilter.GaussianBlur(50)))

    img = apply_rounded_mask(img)
    return img


def save_ico(base: Image.Image, ico_path: Path):
    """Downsample base to all required ICO sizes and write the .ico file."""
    sized = []
    for s in ICO_SIZES:
        res = base.resize((s, s), Image.LANCZOS)
        if s <= 32:
            arr = np.array(res).astype(np.float32)
            g_mask = arr[:,:,1] > 50
            arr[g_mask, 1] = np.clip(arr[g_mask, 1] * 1.5, 0, 255)
            arr[g_mask, 0] = np.clip(arr[g_mask, 0] * 0.5, 0, 255)
            arr[g_mask, 2] = np.clip(arr[g_mask, 2] * 0.7, 0, 255)
            res = Image.fromarray(arr.astype(np.uint8))
        sized.append(res)
        res.save(ICON_DIR / f"icon_{s}x{s}.png")

    sized[0].save(
        str(ico_path),
        format='ICO',
        sizes=[(s, s) for s in ICO_SIZES],
        append_images=sized[1:]
    )
    print(f"[OK] ICO saved: {ico_path}  ({ico_path.stat().st_size:,} bytes)")
    for s in ICO_SIZES:
        print(f"      + icon_{s}x{s}.png")


def main():
    source = sys.argv[1] if len(sys.argv) > 1 else None

    if source:
        print(f"[icon] Building from source: {source}")
        base = build_from_source(source)
    else:
        print("[icon] No source supplied – building procedural icon...")
        base = build_procedural(1024)

    # Save master PNG
    png_path = ICON_DIR / "ghostrigger_icon.png"
    base.save(str(png_path))
    print(f"[OK] PNG saved: {png_path}")

    hi_png = ICON_DIR / "ghostrigger_1024x1024.png"
    base.save(str(hi_png))

    # Save ICO
    ico_path = ICON_DIR / "ghostrigger.ico"
    save_ico(base, ico_path)

    print("\n[icon] Done! Use in PyInstaller spec:")
    print(f"       icon='assets/icons/ghostrigger.ico'")


if __name__ == "__main__":
    main()
