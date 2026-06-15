#pragma once

#include "GhostRiggerAdaptersQtAutorig.h"

namespace ghostrigger::adapters::qt::autorig {

bool qt_application_running();
// run_cloth_preset_dialog returns JSON in thread-local storage.
// Caller must copy the returned value before any subsequent call on the same thread.
const char* run_cloth_preset_dialog(
    const void* parent,
    const char* default_preset,
    const char* title,
    const char* message
);
bool confirm_cloth_action(const void* parent, const char* title, const char* message);
// Returns false only when native UI confirms "No"; returns true when UI is unavailable.

} // namespace ghostrigger::adapters::qt::autorig

extern "C" {
GHOSTRIGGER_ADAPTERS_QT_AUTORIG_API int gr_adapters_qt_autorig_qt_application_running();
GHOSTRIGGER_ADAPTERS_QT_AUTORIG_API const char* gr_adapters_qt_autorig_run_cloth_preset_dialog(
    const void* parent,
    const char* default_preset,
    const char* title,
    const char* message
);
GHOSTRIGGER_ADAPTERS_QT_AUTORIG_API int gr_adapters_qt_autorig_confirm_cloth_action(
    const void* parent,
    const char* title,
    const char* message
);
}
