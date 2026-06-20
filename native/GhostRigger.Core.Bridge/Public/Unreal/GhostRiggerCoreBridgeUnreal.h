#pragma once

#ifdef GHOSTRIGGER_CORE_BRIDGE_UNREAL_EXPORTS
#define GHOSTRIGGER_CORE_BRIDGE_UNREAL_API __declspec(dllexport)
#else
#define GHOSTRIGGER_CORE_BRIDGE_UNREAL_API __declspec(dllimport)
#endif

extern "C" {
GHOSTRIGGER_CORE_BRIDGE_UNREAL_API const char* gr_unreal_version();
GHOSTRIGGER_CORE_BRIDGE_UNREAL_API const char* gr_unreal_capabilities_json();
GHOSTRIGGER_CORE_BRIDGE_UNREAL_API const char* gr_core_bridge_unreal_owner_boundary_json();
GHOSTRIGGER_CORE_BRIDGE_UNREAL_API const char* gr_unreal_dependency_schema_json();
}