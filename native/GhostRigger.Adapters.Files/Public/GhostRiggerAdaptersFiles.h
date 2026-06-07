#pragma once

#ifdef GHOSTRIGGER_ADAPTERS_FILES_EXPORTS
#define GHOSTRIGGER_ADAPTERS_FILES_API __declspec(dllexport)
#else
#define GHOSTRIGGER_ADAPTERS_FILES_API __declspec(dllimport)
#endif

extern "C" {
GHOSTRIGGER_ADAPTERS_FILES_API const char* gr_adapters_files_version();
GHOSTRIGGER_ADAPTERS_FILES_API const char* gr_adapters_files_capabilities_json();
GHOSTRIGGER_ADAPTERS_FILES_API const char* gr_adapters_files_owner_boundary_json();
GHOSTRIGGER_ADAPTERS_FILES_API const char* gr_adapters_files_dependency_schema_json();
}