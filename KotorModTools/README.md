# KotorModTools v1.0
### Odyssey Engine Pipeline Tool — KotOR 1 & KotOR 2 TSL

---

## What It Does

A **one-stop pipeline** for modding Star Wars: Knights of the Old Republic and The Sith Lords.

### Features

| Feature | Description |
|---|---|
| **Game Library Browser** | Browse K1/K2 models directly from game files (KEY/BIF/ERF/RIM archives) |
| **3D Viewport** | Real-time 3D renderer — orbit/pan/zoom, wireframe, bone overlay |
| **Auto-Rigger** | Automatic bone weight assignment to KotOR humanoid/creature skeleton |
| **OBJ Import** | Import `.obj` + `.mtl` with UVs, normals, textures |
| **FBX Import** | Import `.fbx` with rigging, UVs, textures (requires `pyassimp`) |
| **OBJ Export** | Export any loaded model to `.obj` + `.mtl` |
| **FBX Export** | Export to `.fbx` (requires `pyassimp`) |
| **ASCII MDL Write** | Write KotOR-compatible ASCII MDL for MDLOps compilation |
| **MDLOps Bridge** | One-click compile/decompile via MDLOps |
| **TGA → TPC** | Convert TGA textures to Odyssey TPC format with mipmaps |
| **TPC → TGA** | Extract TPC textures back to TGA for editing |
| **Bone Retargeting** | Auto-map FBX bone names → KotOR naming convention |

---

## Quick Start

### Extract to Your KotorModTools Folder

Place `KotorModTools.exe` anywhere. Recommended:
```
Desktop/KotorModTools/
    KotorModTools.exe
    mdlops.pl          ← optional, from ndixUR/mdlops
    work/              ← your working MDL files
```

### Setup Game Directories

1. Launch `KotorModTools.exe`
2. In the **Library** panel, click **Set K1 Dir** and point to your KotOR 1 installation folder (e.g. `C:\Program Files (x86)\Steam\steamapps\common\swkotor`)
3. Click **Set K2 Dir** for KotOR 2 (optional)
4. Click **⟳ Scan** — all models will be listed

### ZBrush / Maya Workflow (High-Fidelity Retopo)

```
[Game]
  └─ Browse Library → Load model in viewport
  └─ Export OBJ (File → Export OBJ)
  └─ Send to ZBrush / Maya for high-poly sculpt

[ZBrush / Maya]
  └─ Sculpt details on high-poly
  └─ Bake normals / AO to low-poly mesh
  └─ Export low-poly as .obj or .fbx

[KotorModTools]
  └─ Import OBJ/FBX (File → Import)
  └─ Auto-Rig (🦴 Auto-Rig button or Rig tab)
  └─ Set Supermodel (e.g. k_sup_males)
  └─ Save ASCII MDL (File → Save ASCII MDL)
  └─ Compile → Binary MDL (MDLOps → Compile)
  └─ Copy .mdl + .mdx + .tpc to game override folder
```

---

## MDLOps Integration

KotorModTools uses [MDLOps by ndixUR](https://github.com/ndixUR/mdlops) to compile
ASCII text MDL files into KotOR's binary format.

**To set up:**
1. Download `mdlops.pl` from [github.com/ndixUR/mdlops](https://github.com/ndixUR/mdlops)
2. Install [Strawberry Perl](https://strawberryperl.com/) (Windows)
3. In KotorModTools: **MDLOps → Set MDLOps Path** → select `mdlops.pl`

---

## KotOR Skeleton Bone Names

KotorModTools auto-rigs to the standard KotOR humanoid skeleton:

```
torsocam (root)
└── hip
    ├── stomach → chest → neck → head
    │             ├── lshoulder → lforearm → lhand → lfinger01/02
    │             └── rshoulder → rforearm → rhand → rfinger01/02
    ├── lthigh → lcalf → lankle → ltoebase
    └── rthigh → rcalf → rankle → rtoebase
```

**Supermodels** provide the base animations — your model inherits them:
- `k_sup_males` / `k_sup_females` — humanoid characters
- `k_sup_creatures` — creatures

---

## Texture Pipeline

```
ZBrush/Substance → .tga (32-bit RGBA or 24-bit RGB)
  ↓ KotorModTools Texture tab → TGA → TPC
  ↓ Optionally add TXI metadata:
      bumpmap          my_texture_n     (normal map)
      envmaptexture    CM_Baremetal     (environment map)
      mipmap           1
  ↓ Place .tpc in override/
```

---

## File Formats Supported

| Format | Read | Write | Notes |
|--------|------|-------|-------|
| `.mdl` binary | ✅ K1+K2 | ✅ via MDLOps | K2 has 8 extra bytes per mesh node |
| `.mdl` ASCII  | ✅ | ✅ | Text format for MDLOps |
| `.mdx` binary | ✅ | ✅ | Vertex data (normals, UVs, weights) |
| `.obj` | ✅ | ✅ | Full UV/normal support |
| `.fbx` | ✅* | ✅* | *Requires pyassimp |
| `.tga` | ✅ | ✅ | 8/24/32-bit |
| `.tpc` | ✅ | ✅ | Odyssey proprietary with mips |
| `.erf/.rim/.mod` | ✅ | — | Module archives |
| KEY/BIF | ✅ | — | Main game archives |

---

## Optional Dependencies

For FBX support:
```
pip install pyassimp
```

For full DXT texture decompression:
```
pip install imageio[freeimage]
```

---

## Source Code

Built on top of [mdlops by ndixUR](https://github.com/ndixUR/mdlops) (GPL-3.0).

Format research from:
- Chuck Chargin Jr. (original mdlops)
- MagnusII (KAurora)
- [deadlystream.com](https://deadlystream.com) community
- [KotOR Modding Wiki](https://kotor-modding.fandom.com/wiki/MDL_Format)
