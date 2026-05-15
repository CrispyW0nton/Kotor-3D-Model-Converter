# D20-M Reference Truth — How KotOR Engines Handle Vertex Transforms

## Source Code Examined
- xoreos: src/graphics/aurora/model_kotor.cpp (readMesh, readSkin)
- KotOR.js: src/odyssey/OdysseyModelNodeMesh.ts (readBinary)
- KotOR.js: src/three/odyssey/OdysseyModel3D.ts (FromMDL, NodeMeshBuilder)

## What Do MESH, SKIN, AABB Flags Mean?

From xoreos model_kotor.cpp:
```cpp
static const int kNodeFlagHasMesh      = 0x0020;
static const int kNodeFlagHasSkin      = 0x0040;
static const int kNodeFlagHasAABB      = 0x0200;
```

- **MESH (0x0020)**: Node has a trimesh (triangle mesh) with vertices, normals,
  UVs, faces. This is standard static geometry (walls, floors, rigid objects).
- **SKIN (0x0040)**: Node has skinning data — bone weights, bone indices, bone
  mapping. Appears IN ADDITION to MESH (flags = 0x0060 = MESH|SKIN). Skin nodes
  are deformed by a bone palette at runtime.
- **AABB (0x0200)**: Node has axis-aligned bounding box data. Used for walkmesh
  and collision trees. NOT used for rendering geometry.

KotOR.js confirms identical flags:
```typescript
OdysseyModelNodeType.Mesh = 0x0020  // from enum
OdysseyModelNodeType.Skin = 0x0040
OdysseyModelNodeType.AABB = 0x0200
```

## Are Skin Vertices "Already World-Space"?

**NO.** Both reference engines store skin vertices in the SAME coordinate space
as regular mesh vertices — node-local. The difference is that SKIN nodes get
deformed by bones at runtime.

### xoreos evidence (readMesh + readSkin):
```cpp
// readMesh: reads vertex positions from MDX data — raw floats, no transform
iv[0] = ctx.mdx->readIEEEFloatLE();  // position X
iv[1] = ctx.mdx->readIEEEFloatLE();  // position Y
iv[2] = ctx.mdx->readIEEEFloatLE();  // position Z
*v++ = iv[0]; *v++ = iv[1]; *v++ = iv[2];
```
There is NO world_transform call during vertex read. Positions are stored as-is.

```cpp
// readSkin: reads bone weights and bone indices ONLY — no vertex transform
vertexData[0] = ctx.mdx->readIEEEFloatLE();  // bone weight 0
vertexData[1] = ctx.mdx->readIEEEFloatLE();  // bone weight 1
// ... etc
```
readSkin does NOT modify vertex positions. It only adds weight/index data.

### KotOR.js evidence (OdysseyModelNodeMesh.ts):
```typescript
// Vertex read: raw from MDX, no transform
if(this.MDXDataBitmap & OdysseyModelMDXFlag.VERTEX){
    this.odysseyModel.mdxReader.position = basePosition + this.MDXVertexOffset;
    this.vertices.push(
        this.odysseyModel.mdxReader.readSingle(),
        this.odysseyModel.mdxReader.readSingle(),
        this.odysseyModel.mdxReader.readSingle()
    );
}
```
Pure read, no matrix multiplication, no world transform.

### KotOR.js evidence (OdysseyModel3D.ts NodeMeshBuilder):
```typescript
// Standard path: vertex positions go directly into buffer attribute
geometry.setAttribute('position',
    new THREE.Float32BufferAttribute(odysseyNode.vertices, 3));
```
Vertices uploaded to GPU as-is. THREE.js applies the node's `matrixWorld`
(accumulated from parent chain) during rendering.

For SKIN nodes:
```typescript
mesh = new THREE.SkinnedMesh(geometry, material);
```
SkinnedMesh lets the GPU deform via bone matrices. No CPU pre-baking.

For STATIC MERGED rooms (mergeStatic=true):
```typescript
parentNode.getWorldPosition(mesh.position);
parentNode.getWorldQuaternion(mesh.quaternion);
mesh.updateMatrix();
(geometry.getAttribute('position')).applyMatrix4(mesh.matrix);
```
This is the ONLY case where vertices are CPU-transformed, and it's for
static room merging (optimization), not because the data is in a different
space.

## Where Are Transforms Actually Applied?

### xoreos:
Transform is applied via OpenGL model matrix. The `render()` call in model.cpp
accumulates the parent chain into a `_absolutePosition` matrix and sets it as
the model-view matrix before drawing.
- Vertices uploaded to VBO: **node-local**
- Transform during draw: **model matrix uniform (GPU)**

### KotOR.js:
Transform is handled by THREE.js scene graph. Each node is a `THREE.Object3D`
with `position` and `quaternion` set from MDL controllers. THREE.js computes
`matrixWorld` by walking the parent chain.
- Vertices uploaded to BufferGeometry: **node-local**
- Transform during draw: **matrixWorld uniform (GPU)**

### Summary of reference engines:
| Engine    | Vertex storage | Transform for draw | CPU pre-bake |
|-----------|---------------|-------------------|-------------|
| xoreos    | Node-local    | Model matrix (GPU) | Never       |
| KotOR.js  | Node-local    | matrixWorld (GPU)   | Only mergeStatic rooms |

## Is Any Centroid/World-Space Guessing Used?

**NO.** Neither xoreos nor KotOR.js uses any centroid magnitude check, world-space
threshold, or vertex-statistics heuristic to decide transforms. The transform
decision is purely structural:
1. Is the node a child of a parent? → Apply parent's transform in the matrix chain.
2. Is the node skinned? → Apply bone palette deformation.
3. Period.

The current GhostRigger heuristic `_WORLDSPACE_VERT_THRESHOLD = 1.5` (centroid
magnitude check) has NO basis in any reference engine. It is a workaround that
treats the SYMPTOM (wrong positioning) rather than the CAUSE (wrong transform path).

## Implications for GhostRigger

GhostRigger's CPU-bake approach (transform vertices on CPU, upload world-space
to VBO) is valid IF AND ONLY IF:
1. Each node's vertices are transformed EXACTLY ONCE by the correct world_transform.
2. The bounds computation uses the SAME transform as the VBO builder.
3. No centroid heuristics are used — the transform decision comes from node flags.

The current code violates all three: it uses centroid-magnitude to guess world-space,
applies different transforms in _build_vbo_data vs _compute_model_bounds vs
compute_bounds, and leaves room for double/zero transforms.
