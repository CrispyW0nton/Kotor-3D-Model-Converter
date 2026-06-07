#pragma once

#ifdef GHOSTRIGGER_MEASUREMENT_EXPORTS
#define GHOSTRIGGER_MEASUREMENT_API __declspec(dllexport)
#else
#define GHOSTRIGGER_MEASUREMENT_API __declspec(dllimport)
#endif

extern "C" {
GHOSTRIGGER_MEASUREMENT_API const char* gr_measurement_version();
GHOSTRIGGER_MEASUREMENT_API const char* gr_measurement_capabilities_json();
GHOSTRIGGER_MEASUREMENT_API const char* gr_measurement_owner_boundary_json();
GHOSTRIGGER_MEASUREMENT_API const char* gr_measurement_dependency_schema_json();
}