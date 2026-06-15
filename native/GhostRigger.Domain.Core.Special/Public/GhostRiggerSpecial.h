#pragma once

#ifdef GHOSTRIGGER_SPECIAL_EXPORTS
#define GHOSTRIGGER_SPECIAL_API __declspec(dllexport)
#else
#define GHOSTRIGGER_SPECIAL_API __declspec(dllimport)
#endif

extern "C" {
GHOSTRIGGER_SPECIAL_API const char* gr_special_version();
GHOSTRIGGER_SPECIAL_API const char* gr_special_capabilities_json();
GHOSTRIGGER_SPECIAL_API const char* gr_special_owner_boundary_json();
GHOSTRIGGER_SPECIAL_API const char* gr_special_dependency_schema_json();
}