from __future__ import annotations

from typing import TypeVar


T = TypeVar("T")


class _KnownNoisyGFFStruct:
    def __init__(self, fields=None):
        self._fields = dict(fields or {})

    def exists(self, label):
        return label in self._fields

    def __getitem__(self, label):
        return self._fields[label]

    def acquire(self, label, default, object_type=None):
        default_cls = default.__class__
        assert isinstance(default, object), f"{default_cls.__name__}: {default}"
        value: T = default
        if object_type is None:
            object_type = default_cls
        if self.exists(label) and object_type is not None:
            value = self[label]
            try:
                print(f"value: {value} cls: {value.__class__} (isinstance? {isinstance(value, object_type)} {object_type})")
            except Exception:
                ...
        if object_type is bool and issubclass(value.__class__, int):
            value = bool(value)
        return value


class _CleanUpstreamGFFStruct:
    def __init__(self, fields=None):
        self._fields = dict(fields or {})

    def exists(self, label):
        return label in self._fields

    def __getitem__(self, label):
        return self._fields[label]

    def acquire(self, label, default, object_type=None):
        default_cls = default.__class__
        assert isinstance(default, object), f"{default_cls.__name__}: {default}"
        value: T = default
        if object_type is None:
            object_type = default_cls
        if self.exists(label) and object_type is not None:
            value = self[label]
        if object_type is bool and issubclass(value.__class__, int):
            value = bool(value)
        return value


def test_known_pykotor_debug_acquire_becomes_quiet_with_value_and_bool_parity(capsys) -> None:
    from src.core.game.pykotor_gff_runtime_fix import ensure_pykotor_gff_acquire_quiet

    status = ensure_pykotor_gff_acquire_quiet(_KnownNoisyGFFStruct)

    assert status["status"] == "patched"
    assert status["applied"] is True
    assert status["changed"] is True

    struct = _KnownNoisyGFFStruct(
        {"count": 7, "enabled": 1, "disabled": 0, "legacy_mismatch": "kept"}
    )
    assert struct.acquire("missing", 23) == 23
    assert struct.acquire("count", 0) == 7
    assert struct.acquire("enabled", False, bool) is True
    assert struct.acquire("disabled", True, bool) is False
    # Preserve the released implementation's actual behavior: it returns an
    # existing value even when it does not match the requested object type.
    assert struct.acquire("legacy_mismatch", 0, int) == "kept"
    assert capsys.readouterr().out == ""


def test_quiet_guard_is_idempotent() -> None:
    from src.core.game.pykotor_gff_runtime_fix import ensure_pykotor_gff_acquire_quiet

    ensure_pykotor_gff_acquire_quiet(_KnownNoisyGFFStruct)
    first = _KnownNoisyGFFStruct.acquire
    status = ensure_pykotor_gff_acquire_quiet(_KnownNoisyGFFStruct)

    assert _KnownNoisyGFFStruct.acquire is first
    assert status["status"] == "already_patched"
    assert status["applied"] is True
    assert status["changed"] is False


def test_clean_upstream_acquire_is_left_untouched() -> None:
    from src.core.game.pykotor_gff_runtime_fix import ensure_pykotor_gff_acquire_quiet

    original = _CleanUpstreamGFFStruct.acquire
    status = ensure_pykotor_gff_acquire_quiet(_CleanUpstreamGFFStruct)

    assert _CleanUpstreamGFFStruct.acquire is original
    assert status["status"] == "upstream_clean"
    assert status["applied"] is False
    assert status["changed"] is False


def test_resource_manager_runs_guard_before_stock_module_use(monkeypatch) -> None:
    from src.core.assets import resource_manager as resource_manager_module

    calls = []
    expected = {
        "checked": True,
        "status": "test_guard",
        "applied": True,
        "changed": False,
    }

    def _guard():
        calls.append("called")
        return dict(expected)

    monkeypatch.setattr(
        resource_manager_module,
        "ensure_pykotor_gff_acquire_quiet",
        _guard,
    )

    manager = resource_manager_module.ResourceManager()

    assert calls == ["called"]
    assert manager._pykotor_gff_runtime_fix_status == expected
