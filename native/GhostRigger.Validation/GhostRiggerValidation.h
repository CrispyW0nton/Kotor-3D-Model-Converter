#pragma once

#ifdef GHOSTRIGGER_VALIDATION_EXPORTS
#define GHOSTRIGGER_VALIDATION_API __declspec(dllexport)
#else
#define GHOSTRIGGER_VALIDATION_API __declspec(dllimport)
#endif

extern "C" {
GHOSTRIGGER_VALIDATION_API const char* gr_validation_version();
GHOSTRIGGER_VALIDATION_API const char* gr_validation_capabilities_json();
GHOSTRIGGER_VALIDATION_API const char* gr_validation_owner_boundary_json();
GHOSTRIGGER_VALIDATION_API const char* gr_validation_dependency_schema_json();
}