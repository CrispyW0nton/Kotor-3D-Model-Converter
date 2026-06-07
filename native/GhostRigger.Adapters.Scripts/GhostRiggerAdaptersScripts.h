#pragma once

#ifdef GHOSTRIGGER_ADAPTERS_SCRIPTS_EXPORTS
#define GHOSTRIGGER_ADAPTERS_SCRIPTS_API __declspec(dllexport)
#else
#define GHOSTRIGGER_ADAPTERS_SCRIPTS_API __declspec(dllimport)
#endif

extern "C" {
GHOSTRIGGER_ADAPTERS_SCRIPTS_API const char* gr_adapters_scripts_version();
GHOSTRIGGER_ADAPTERS_SCRIPTS_API const char* gr_adapters_scripts_capabilities_json();
GHOSTRIGGER_ADAPTERS_SCRIPTS_API const char* gr_adapters_scripts_owner_boundary_json();
GHOSTRIGGER_ADAPTERS_SCRIPTS_API const char* gr_adapters_scripts_dependency_schema_json();
}