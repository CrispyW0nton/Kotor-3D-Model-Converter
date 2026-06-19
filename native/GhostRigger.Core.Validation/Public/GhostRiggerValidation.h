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
GHOSTRIGGER_VALIDATION_API int gr_validation_severity_rank(const char* severity);
GHOSTRIGGER_VALIDATION_API int gr_validation_is_valid_severity(const char* severity);
GHOSTRIGGER_VALIDATION_API int gr_validation_is_valid_subsystem(const char* subsystem);
GHOSTRIGGER_VALIDATION_API const char* gr_validation_severity_values_json();
GHOSTRIGGER_VALIDATION_API const char* gr_validation_subsystem_values_json();
GHOSTRIGGER_VALIDATION_API const char* gr_validation_validation_bus_schema_json();
}
