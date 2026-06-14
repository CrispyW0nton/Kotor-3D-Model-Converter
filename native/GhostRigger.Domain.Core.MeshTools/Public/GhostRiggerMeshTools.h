#pragma once

#ifdef GHOSTRIGGER_MESH_TOOLS_EXPORTS
#define GHOSTRIGGER_MESH_TOOLS_API __declspec(dllexport)
#else
#define GHOSTRIGGER_MESH_TOOLS_API __declspec(dllimport)
#endif

extern "C" {
GHOSTRIGGER_MESH_TOOLS_API const char* gr_mesh_tools_version();
GHOSTRIGGER_MESH_TOOLS_API const char* gr_mesh_tools_capabilities_json();
GHOSTRIGGER_MESH_TOOLS_API const char* gr_mesh_tools_owner_boundary_json();
GHOSTRIGGER_MESH_TOOLS_API const char* gr_mesh_tools_dependency_schema_json();
GHOSTRIGGER_MESH_TOOLS_API const char* gr_mesh_tools_command_schema_json();
}
