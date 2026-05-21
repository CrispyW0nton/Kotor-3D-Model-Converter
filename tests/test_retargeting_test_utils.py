from src.core.retargeting.test_utils import filter_stock_animations


def test_filter_stock_animations_removes_external_artifacts():
    names = [
        "walk",
        "g1a1",
        "custom_mixamo_a1",
        "resolver_smoke_test",
        "foo_patch",
        "mixamo_walk",
        "test_clip",
    ]

    assert filter_stock_animations(names) == ["walk", "g1a1"]
