#pragma once

#ifdef GHOSTRIGGER_CONVERTERS_EXPORTS
#define GHOSTRIGGER_CONVERTERS_API __declspec(dllexport)
#else
#define GHOSTRIGGER_CONVERTERS_API __declspec(dllimport)
#endif

extern "C" {
GHOSTRIGGER_CONVERTERS_API const char* gr_converters_version();
GHOSTRIGGER_CONVERTERS_API const char* gr_converters_capabilities_json();
GHOSTRIGGER_CONVERTERS_API const char* gr_converters_owner_boundary_json();
GHOSTRIGGER_CONVERTERS_API const char* gr_converters_dependency_schema_json();
}