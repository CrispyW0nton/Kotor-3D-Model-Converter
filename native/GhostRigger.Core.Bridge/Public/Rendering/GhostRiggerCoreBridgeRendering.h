#pragma once

#ifdef GHOSTRIGGER_CORE_BRIDGE_RENDERING_EXPORTS
#define GHOSTRIGGER_CORE_BRIDGE_RENDERING_API __declspec(dllexport)
#else
#define GHOSTRIGGER_CORE_BRIDGE_RENDERING_API __declspec(dllimport)
#endif

extern "C" {
GHOSTRIGGER_CORE_BRIDGE_RENDERING_API const char* gr_core_bridge_rendering_version();
GHOSTRIGGER_CORE_BRIDGE_RENDERING_API const char* gr_core_bridge_rendering_capabilities_json();
GHOSTRIGGER_CORE_BRIDGE_RENDERING_API const char* gr_core_bridge_rendering_owner_boundary_json();
GHOSTRIGGER_CORE_BRIDGE_RENDERING_API const char* gr_core_bridge_rendering_dependency_schema_json();
}