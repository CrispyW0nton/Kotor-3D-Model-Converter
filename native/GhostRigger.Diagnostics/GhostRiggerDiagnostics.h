#pragma once

#ifdef GHOSTRIGGER_DIAGNOSTICS_EXPORTS
#define GHOSTRIGGER_DIAGNOSTICS_API __declspec(dllexport)
#else
#define GHOSTRIGGER_DIAGNOSTICS_API __declspec(dllimport)
#endif

extern "C" {
GHOSTRIGGER_DIAGNOSTICS_API const char* gr_diagnostics_version();
GHOSTRIGGER_DIAGNOSTICS_API const char* gr_diagnostics_capabilities_json();
GHOSTRIGGER_DIAGNOSTICS_API const char* gr_diagnostics_owner_boundary_json();
GHOSTRIGGER_DIAGNOSTICS_API const char* gr_diagnostics_dependency_schema_json();
}