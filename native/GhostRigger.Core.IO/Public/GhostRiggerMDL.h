#pragma once

#ifdef GHOSTRIGGER_MDL_EXPORTS
#define GHOSTRIGGER_MDL_API __declspec(dllexport)
#else
#define GHOSTRIGGER_MDL_API __declspec(dllimport)
#endif

extern "C" {
GHOSTRIGGER_MDL_API const char* gr_mdl_version();
GHOSTRIGGER_MDL_API const char* gr_mdl_capabilities_json();
GHOSTRIGGER_MDL_API const char* gr_mdl_owner_boundary_json();
GHOSTRIGGER_MDL_API const char* gr_mdl_dependency_schema_json();
}