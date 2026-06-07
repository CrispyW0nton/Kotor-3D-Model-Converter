#pragma once

#ifdef GHOSTRIGGER_ADAPTERS_QT_AUTORIG_EXPORTS
#define GHOSTRIGGER_ADAPTERS_QT_AUTORIG_API __declspec(dllexport)
#else
#define GHOSTRIGGER_ADAPTERS_QT_AUTORIG_API __declspec(dllimport)
#endif

extern "C" {
GHOSTRIGGER_ADAPTERS_QT_AUTORIG_API const char* gr_adapters_qt_autorig_version();
GHOSTRIGGER_ADAPTERS_QT_AUTORIG_API const char* gr_adapters_qt_autorig_capabilities_json();
GHOSTRIGGER_ADAPTERS_QT_AUTORIG_API const char* gr_adapters_qt_autorig_owner_boundary_json();
GHOSTRIGGER_ADAPTERS_QT_AUTORIG_API const char* gr_adapters_qt_autorig_dependency_schema_json();
}