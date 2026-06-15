#pragma once

#ifdef GHOSTRIGGER_UNREAL_EXPORTS
#define GHOSTRIGGER_UNREAL_API __declspec(dllexport)
#else
#define GHOSTRIGGER_UNREAL_API __declspec(dllimport)
#endif

extern "C" {
GHOSTRIGGER_UNREAL_API const char* gr_unreal_version();
GHOSTRIGGER_UNREAL_API const char* gr_unreal_capabilities_json();
GHOSTRIGGER_UNREAL_API const char* gr_unreal_owner_boundary_json();
GHOSTRIGGER_UNREAL_API const char* gr_unreal_dependency_schema_json();
}