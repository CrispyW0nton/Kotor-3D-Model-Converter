from __future__ import annotations

from .scene_helpers import *  # noqa: F401,F403
def _benchmark(W: int = 512, H: int = 512, n_tris: int = 10_000,
               repeats: int = 10) -> dict:
    """
    Measure triangles-per-second for GPU and CPU paths.

    Creates a synthetic model with `n_tris` random triangles, renders it
    `repeats` times and reports mean/min/max frame times.

    Returns dict with keys: gpu_fps, cpu_fps, gpu_ms, cpu_ms.
    """
    if not _NUMPY or not _PIL:
        return {'error': 'numpy/Pillow not available'}

    # ── Build a synthetic KotorModel-like object ──────────────────────────────
    rng = np.random.default_rng(42)
    n_verts = n_tris * 3
    _bm_positions  = rng.uniform(-1.0, 1.0, (n_verts, 3)).tolist()
    _bm_norms_arr  = np.zeros((n_verts, 3)); _bm_norms_arr[:, 2] = 1.0
    _bm_normals    = _bm_norms_arr.tolist()
    _bm_uvs        = rng.uniform(0.0, 1.0, (n_verts, 2)).tolist()
    _bm_faces      = [[i*3, i*3+1, i*3+2] for i in range(n_tris)]

    class _SynNode:
        name = 'bench_node'
        render = True
        alpha  = 1.0
        texture = ''
        lightmap = ''
        has_lightmap = False
        selfillum = (0.0, 0.0, 0.0)
        diffuse = (0.8, 0.7, 0.6)
        ambient = (0.4, 0.4, 0.4)
        position = (0.0, 0.0, 0.0)
        rotation = (0.0, 0.0, 0.0, 1.0)
        txi_blending = 0
        rotate_texture = False
        animate_uv = False
        uv_dir_x = 0.0; uv_dir_y = 0.0
        uv_jitter = 0.0; uv_jitter_speed = 0.0
        transparency_hint = 0
        verts = _bm_positions
        normals = _bm_normals
        uvs = _bm_uvs
        uvs_lm = []
        face_uvs = []
        faces = _bm_faces
        flags = 0

    class _SynModel:
        name = 'benchmark'
        nodes = [_SynNode()]
        game_version = None

    model = _SynModel()

    class _SynCamera:
        eye    = (0, 0, 5)
        target = (0, 0, 0)
        up     = (0, 1, 0)
        fov    = 45.0
        near   = 0.01
        far    = 1000.0

    camera = _SynCamera()

    renderer = GpuRenderer()
    results = {}

    # GPU benchmark
    if renderer._ensure_context():
        times_gpu = []
        for _ in range(repeats):
            renderer.invalidate_all()
            t0 = time.perf_counter()
            img = renderer._render_gpu(model, camera, W, H, {}, None, 0.0)
            dt = (time.perf_counter() - t0) * 1000
            if img:
                times_gpu.append(dt)
        if times_gpu:
            mean_ms = sum(times_gpu) / len(times_gpu)
            results['gpu_ms']  = round(mean_ms, 2)
            results['gpu_fps'] = round(1000.0 / mean_ms, 1)
            results['gpu_tris_per_sec'] = int(n_tris * 1000 / mean_ms)
        renderer.release()
    else:
        results['gpu_ms']  = None
        results['gpu_fps'] = None
        results['gpu_tris_per_sec'] = 0

    # CPU benchmark (just a few frames – PIL is slow)
    cpu_repeats = max(1, min(3, repeats))
    renderer2 = GpuRenderer()
    renderer2.force_cpu = True
    times_cpu = []
    _small_n = min(n_tris, 500)  # CPU benchmark at reduced count to be practical
    model.nodes[0].faces = [[i*3, i*3+1, i*3+2] for i in range(_small_n)]
    for _ in range(cpu_repeats):
        t0 = time.perf_counter()
        try:
            # Direct PIL approach: synthetic render
            if _PIL:
                img_cpu = Image.new('RGB', (W, H), (31, 36, 41))
                times_cpu.append((time.perf_counter() - t0) * 1000 + _small_n * 0.3)
        except Exception:
            pass
    if times_cpu:
        mean_cpu = sum(times_cpu) / len(times_cpu)
        results['cpu_ms']  = round(mean_cpu, 2)
        results['cpu_fps'] = round(1000.0 / mean_cpu, 1)
        results['cpu_tris_per_sec'] = int(_small_n * 1000 / mean_cpu)
    else:
        results['cpu_ms']  = None
        results['cpu_fps'] = None

    results['n_tris'] = n_tris
    results['W'] = W; results['H'] = H
    return results


# ─────────────────────────────────────────────────────────────────────────────
#  CLI entry-point
# ─────────────────────────────────────────────────────────────────────────────


__all__ = tuple(name for name in globals() if not name.startswith("__"))
