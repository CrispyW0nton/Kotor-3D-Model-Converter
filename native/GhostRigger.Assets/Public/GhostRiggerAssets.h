#pragma once

#ifdef GHOSTRIGGER_ASSETS_EXPORTS
#define GHOSTRIGGER_ASSETS_API __declspec(dllexport)
#else
#define GHOSTRIGGER_ASSETS_API __declspec(dllimport)
#endif

extern "C" {
GHOSTRIGGER_ASSETS_API const char* gr_assets_version();
GHOSTRIGGER_ASSETS_API const char* gr_assets_capabilities_json();
GHOSTRIGGER_ASSETS_API const char* gr_assets_owner_boundary_json();
GHOSTRIGGER_ASSETS_API const char* gr_assets_dependency_schema_json();
}