#pragma once

#ifdef GHOSTRIGGER_CORE_QT_AUTORIG_EXPORTS
#define GHOSTRIGGER_CORE_QT_AUTORIG_API __declspec(dllexport)
#else
#define GHOSTRIGGER_CORE_QT_AUTORIG_API __declspec(dllimport)
#endif

extern "C" {
GHOSTRIGGER_CORE_QT_AUTORIG_API const char* gr_core_qt_autorig_version();
GHOSTRIGGER_CORE_QT_AUTORIG_API const char* gr_core_qt_autorig_capabilities_json();
GHOSTRIGGER_CORE_QT_AUTORIG_API const char* gr_core_qt_autorig_owner_boundary_json();
GHOSTRIGGER_CORE_QT_AUTORIG_API const char* gr_core_qt_autorig_dependency_schema_json();
GHOSTRIGGER_CORE_QT_AUTORIG_API int gr_core_qt_autorig_qt_application_running();
GHOSTRIGGER_CORE_QT_AUTORIG_API const char* gr_core_qt_autorig_run_cloth_preset_dialog(
    const void* parent,
    const char* default_preset,
    const char* title,
    const char* message
);
GHOSTRIGGER_CORE_QT_AUTORIG_API int gr_core_qt_autorig_confirm_cloth_action(
    const void* parent,
    const char* title,
    const char* message
);
}
