#pragma once

#ifdef GHOSTRIGGER_EXPORT_EXPORTS
#define GHOSTRIGGER_EXPORT_API __declspec(dllexport)
#else
#define GHOSTRIGGER_EXPORT_API __declspec(dllimport)
#endif

extern "C" {
GHOSTRIGGER_EXPORT_API const char* gr_export_version();
GHOSTRIGGER_EXPORT_API const char* gr_export_capabilities_json();
GHOSTRIGGER_EXPORT_API const char* gr_export_owner_boundary_json();
GHOSTRIGGER_EXPORT_API const char* gr_export_dependency_schema_json();
}