#pragma once

#ifdef GHOSTRIGGER_SYSTEMS_BAS_EXPORTS
#define GHOSTRIGGER_SYSTEMS_BAS_API __declspec(dllexport)
#else
#define GHOSTRIGGER_SYSTEMS_BAS_API __declspec(dllimport)
#endif

extern "C" {
GHOSTRIGGER_SYSTEMS_BAS_API const char* gr_systems_bas_version();
GHOSTRIGGER_SYSTEMS_BAS_API const char* gr_systems_bas_capabilities_json();
GHOSTRIGGER_SYSTEMS_BAS_API const char* gr_systems_bas_owner_boundary_json();
GHOSTRIGGER_SYSTEMS_BAS_API const char* gr_systems_bas_dependency_schema_json();
}