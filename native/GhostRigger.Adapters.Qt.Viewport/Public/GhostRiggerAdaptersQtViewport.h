#pragma once

#ifdef GHOSTRIGGER_ADAPTERS_QT_VIEWPORT_EXPORTS
#define GHOSTRIGGER_ADAPTERS_QT_VIEWPORT_API __declspec(dllexport)
#else
#define GHOSTRIGGER_ADAPTERS_QT_VIEWPORT_API __declspec(dllimport)
#endif

extern "C" {
GHOSTRIGGER_ADAPTERS_QT_VIEWPORT_API const char* gr_adapters_qt_viewport_version();
GHOSTRIGGER_ADAPTERS_QT_VIEWPORT_API const char* gr_adapters_qt_viewport_capabilities_json();
GHOSTRIGGER_ADAPTERS_QT_VIEWPORT_API const char* gr_adapters_qt_viewport_owner_boundary_json();
GHOSTRIGGER_ADAPTERS_QT_VIEWPORT_API const char* gr_adapters_qt_viewport_dependency_schema_json();
}