#pragma once

#ifdef GHOSTRIGGER_MODULES_EXPORTS
#define GHOSTRIGGER_MODULES_API __declspec(dllexport)
#else
#define GHOSTRIGGER_MODULES_API __declspec(dllimport)
#endif

extern "C" {
GHOSTRIGGER_MODULES_API const char* gr_modules_version();
GHOSTRIGGER_MODULES_API const char* gr_modules_capabilities_json();
GHOSTRIGGER_MODULES_API const char* gr_modules_owner_boundary_json();
GHOSTRIGGER_MODULES_API const char* gr_modules_dependency_schema_json();
}