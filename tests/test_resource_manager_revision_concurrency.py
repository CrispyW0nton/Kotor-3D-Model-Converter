"""Focused contracts for revisioned ResourceManager publication."""

from __future__ import annotations

from types import MethodType, SimpleNamespace
import threading

from src.core.assets import resource_manager as resource_manager_module
from src.core.assets.resource_manager import RES_MDL, RES_MDX, RES_TGA, ResourceManager
from src.core.game import kotor_loader


def test_resource_manager_revision_advances_only_after_successful_publication(tmp_path, monkeypatch) -> None:
    class FakeInstall:
        def __init__(self, path: str, game: str) -> None:
            self.path = path
            self.game = game
            self._key_map = {}
            self._tex_erfs = []
            self._mod_erfs = []
            self._override = {}

        def get(self, _name: str, _res_type: int):
            return None

    monkeypatch.setattr(resource_manager_module, "_GameInstall", FakeInstall)
    manager = ResourceManager()
    assert manager.revision == 0
    assert manager.set_k1_dir(str(tmp_path / "missing")) is False
    assert manager.revision == 0

    k1_dir = tmp_path / "k1"
    k2_dir = tmp_path / "k2"
    k1_dir.mkdir()
    k2_dir.mkdir()
    assert manager.set_k1_dir(str(k1_dir)) is True
    assert manager.revision == 1
    assert manager.set_k2_dir(str(k2_dir)) is True
    assert manager.revision == 2

    loose_dir = tmp_path / "loose"
    loose_dir.mkdir()
    (loose_dir / "player.mdl").write_bytes(b"mdl")
    assert manager.add_loose_overlay(str(loose_dir)) == 1
    assert manager.revision == 3

    manager.clear_module_overlay()
    assert manager.revision == 4


def test_project_overlay_replaces_stale_authored_resources_and_revisions_texture_cache() -> None:
    from src.core.rendering.frame_core.texture_cache import TextureCache

    manager = ResourceManager()
    assert manager.set_project_overlay((("gr_forest", "tga", b"first"),)) == 1
    first_revision = manager.revision
    assert manager.get("gr_forest", RES_TGA, "K1") == b"first"
    assert manager.get_strict("gr_forest", RES_TGA, "K1") == b"first"

    # Republishing identical bytes is stable; replacing the active project
    # evicts the old resource and advances the renderer-visible revision.
    assert manager.set_project_overlay((("gr_forest", ".tga", b"first"),)) == 1
    assert manager.revision == first_revision
    assert manager.set_project_overlay((("gr_cave", RES_TGA, b"second"),)) == 1
    assert manager.revision == first_revision + 1
    assert manager.get("gr_forest", RES_TGA, "K1") is None
    assert manager.get("gr_cave", RES_TGA, "K1") == b"second"

    cache = TextureCache()
    cache.set_resource_manager(manager, "K1")
    cache._cache["gr_cave"] = object()
    manager.set_project_overlay((("gr_cave", "tga", b"third"),))
    cache.set_resource_manager(manager, "K1")
    assert cache._cache == {}


def test_strict_model_pair_is_coherent_and_parse_runs_outside_resource_lock(monkeypatch) -> None:
    manager = ResourceManager()
    mdl_read = threading.Event()
    release_pair = threading.Event()
    parse_started = threading.Event()
    release_parse = threading.Event()
    mutation_started = threading.Event()
    mutation_done = threading.Event()
    reads: list[int] = []

    def fake_get_strict_locked(self, _name: str, res_type: int, _game: str = "K1"):
        reads.append(res_type)
        if res_type == RES_MDL:
            mdl_read.set()
            assert release_pair.wait(2.0)
            return b"mdl-revision-0"
        if res_type == RES_MDX:
            return b"mdx-revision-0"
        return None

    def fake_parse(mdl: bytes, mdx: bytes):
        assert mdl == b"mdl-revision-0"
        assert mdx == b"mdx-revision-0"
        parse_started.set()
        assert release_parse.wait(2.0)
        return SimpleNamespace()

    manager._get_strict_locked = MethodType(fake_get_strict_locked, manager)
    monkeypatch.setattr(kotor_loader, "load_model_from_bytes", fake_parse)
    loaded: list[object] = []
    loader_thread = threading.Thread(
        target=lambda: loaded.append(manager.load_model_strict("player", "K1")),
        daemon=True,
    )
    loader_thread.start()
    assert mdl_read.wait(2.0)

    def mutate() -> None:
        mutation_started.set()
        manager.clear_module_overlay()
        mutation_done.set()

    mutation_thread = threading.Thread(target=mutate, daemon=True)
    mutation_thread.start()
    assert mutation_started.wait(2.0)
    assert not mutation_done.wait(0.05), "resource mutation crossed the locked MDL/MDX capture"

    release_pair.set()
    assert parse_started.wait(2.0)
    assert mutation_done.wait(2.0), "model parsing still held the ResourceManager lock"
    release_parse.set()
    loader_thread.join(2.0)
    mutation_thread.join(2.0)

    assert not loader_thread.is_alive()
    assert not mutation_thread.is_alive()
    assert reads == [RES_MDL, RES_MDX]
    assert len(loaded) == 1
    assert loaded[0] is not None
    assert manager.revision == 1
