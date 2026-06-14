#pragma once

#ifdef GHOSTRIGGER_FORMATS_EXPORTS
#define GHOSTRIGGER_FORMATS_API __declspec(dllexport)
#else
#define GHOSTRIGGER_FORMATS_API __declspec(dllimport)
#endif

extern "C" {
GHOSTRIGGER_FORMATS_API const char* gr_formats_version();
GHOSTRIGGER_FORMATS_API const char* gr_formats_capabilities_json();
GHOSTRIGGER_FORMATS_API const char* gr_formats_owner_boundary_json();
GHOSTRIGGER_FORMATS_API const char* gr_formats_dependency_schema_json();
}