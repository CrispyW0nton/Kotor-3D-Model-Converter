#pragma once

#ifdef GHOSTRIGGER_AUTORIG_EXPORTS
#define GHOSTRIGGER_AUTORIG_API __declspec(dllexport)
#else
#define GHOSTRIGGER_AUTORIG_API __declspec(dllimport)
#endif

extern "C" {
GHOSTRIGGER_AUTORIG_API const char* gr_autorig_version();
GHOSTRIGGER_AUTORIG_API const char* gr_autorig_capabilities_json();
GHOSTRIGGER_AUTORIG_API const char* gr_autorig_owner_boundary_json();
GHOSTRIGGER_AUTORIG_API const char* gr_autorig_dependency_schema_json();
}