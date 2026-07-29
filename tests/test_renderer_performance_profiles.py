from __future__ import annotations

import os


def test_auto_profile_tunes_reported_integrated_laptop() -> None:
    from src.core.rendering.renderer_settings import RendererSettings

    settings = RendererSettings.from_settings(
        {
            "renderer": {
                "performance_profile": "auto",
                "target_fps": 60,
                "diagnostics_hz": 2.0,
                "bloom_enabled": True,
                "wgpu": {
                    "max_texture_memory_mb": 512,
                    "max_uploads_per_frame": 16,
                },
            }
        },
        hardware={
            "physical_cores": 4,
            "logical_threads": 8,
            "gpu_adapter": "Intel(R) Iris(R) Xe Graphics",
        },
    )

    assert settings.performance_profile == "auto"
    assert settings.effective_performance_profile == "low_power"
    assert settings.target_fps == 45
    assert settings.diagnostics_hz == 1.0
    assert settings.bloom_enabled is False
    assert settings.wgpu_max_texture_memory_mb == 256
    assert settings.wgpu_max_uploads_per_frame == 8
    assert settings.dynamic_quality_large_scene_threshold == 2500


def test_auto_profile_preserves_balanced_discrete_machine_settings() -> None:
    from src.core.rendering.renderer_settings import RendererSettings

    settings = RendererSettings.from_settings(
        {
            "renderer": {
                "performance_profile": "auto",
                "target_fps": 75,
                "bloom_enabled": True,
            }
        },
        hardware={
            "physical_cores": 12,
            "logical_threads": 24,
            "gpu_adapter": "NVIDIA GeForce RTX 4070",
        },
    )

    assert settings.effective_performance_profile == "balanced"
    assert settings.target_fps == 75
    assert settings.bloom_enabled is True


def test_auto_profile_prefers_discrete_gpu_on_hybrid_workstation() -> None:
    from src.core.rendering.renderer_settings import RendererSettings

    settings = RendererSettings.from_settings(
        {"renderer": {"performance_profile": "auto"}},
        hardware={
            "physical_cores": 24,
            "logical_threads": 32,
            "gpu_adapter": (
                "NVIDIA GeForce RTX 5090; Meta Virtual Monitor; "
                "Intel(R) UHD Graphics 770"
            ),
        },
    )

    assert settings.effective_performance_profile == "balanced"


def test_explicit_quality_profile_is_stable_on_integrated_hardware() -> None:
    from src.core.rendering.renderer_settings import RendererSettings

    settings = RendererSettings.from_settings(
        {
            "renderer": {
                "performance_profile": "quality",
                "target_fps": 30,
                "bloom_enabled": False,
            }
        },
        hardware={"physical_cores": 4, "gpu_adapter": "Intel UHD Graphics"},
    )

    assert settings.effective_performance_profile == "quality"
    assert settings.target_fps == 60
    assert settings.bloom_enabled is True
    assert settings.to_settings_dict()["performance_profile"] == "quality"


def test_settings_dialog_reveals_effective_auto_profile() -> None:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

    from PySide6 import QtWidgets

    from src.gui.qt_lib.dialogs.qt_settings_dialog import QtSettingsDialog

    app = QtWidgets.QApplication.instance() or QtWidgets.QApplication([])
    dialog = QtSettingsDialog(
        {"renderer": {"performance_profile": "auto"}},
        hardware_diagnostics={
            "physical_cores": 4,
            "logical_threads": 8,
            "gpu_adapter": "Intel Iris Xe Graphics",
        },
    )
    try:
        assert dialog.renderer_performance_profile_combo.currentData() == "auto"
        assert "Auto selected low power" in dialog.renderer_performance_profile_status.text()
        assert "45 FPS" in dialog.renderer_performance_profile_status.text()
        assert "Choose Custom" in dialog.renderer_performance_profile_status.text()
        assert dialog.renderer_target_fps_spin.isEnabled() is False
        assert dialog.renderer_bloom_check.isEnabled() is False
        assert dialog.values()["renderer"]["performance_profile"] == "auto"
        custom_index = dialog.renderer_performance_profile_combo.findData("custom")
        dialog.renderer_performance_profile_combo.setCurrentIndex(custom_index)
        assert dialog.renderer_target_fps_spin.isEnabled() is True
        assert dialog.renderer_bloom_check.isEnabled() is True
    finally:
        dialog.deleteLater()
        app.processEvents()


def test_gpu_brand_resolution_never_launches_a_hardware_probe(monkeypatch) -> None:
    from src.gui.viewports.viewport_core.shared import icons

    monkeypatch.setenv("GHOSTRIGGER_GPU_ADAPTER", "AMD Radeon RX 7800 XT")
    assert icons._detect_gpu_brand() == "amd"
    monkeypatch.setenv("GHOSTRIGGER_GPU_ADAPTER", "Intel Iris Xe Graphics")
    assert icons._detect_gpu_brand() == "generic"


def test_prelaunch_foreground_default_is_subsecond(monkeypatch) -> None:
    from src.gui.windows.application_core.application_core_lib.functions.app_runner import (
        _prelaunch_foreground_seconds_from_env,
    )

    monkeypatch.delenv("GHOSTRIGGER_PRELAUNCH_FOREGROUND_MS", raising=False)
    assert _prelaunch_foreground_seconds_from_env() == 0.75
    monkeypatch.setenv("GHOSTRIGGER_PRELAUNCH_FOREGROUND_MS", "100")
    assert _prelaunch_foreground_seconds_from_env() == 0.25


def test_matrix_animation_rate_can_drop_for_low_power_mode() -> None:
    os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

    from PySide6 import QtCore

    from src.gui.qt_lib.assets.qt_matrix_background import QtMatrixEngine

    engine = QtMatrixEngine(fps=12)
    assert 80 <= engine.interval_ms <= 84
    engine.start()
    engine.set_fps(4)
    assert engine.interval_ms == 250
    assert engine.timer.interval() == 250
    assert engine.timer.timerType() in {
        QtCore.Qt.TimerType.CoarseTimer,
        QtCore.Qt.TimerType.PreciseTimer,
    }
    engine.stop()
