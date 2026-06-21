#pragma once

#if defined(_WIN32)
#if defined(GHOSTRIGGER_TOOLS_MODULE_MESHES_EXPORTS)
#define GR_TOOLS_MODULE_MESHES_API __declspec(dllexport)
#else
#define GR_TOOLS_MODULE_MESHES_API __declspec(dllimport)
#endif
#else
#define GR_TOOLS_MODULE_MESHES_API
#endif

extern "C" {

GR_TOOLS_MODULE_MESHES_API const char* gr_tools_module_meshes_version();
GR_TOOLS_MODULE_MESHES_API const char* gr_tools_module_meshes_capabilities_json();
GR_TOOLS_MODULE_MESHES_API const char* gr_tools_module_meshes_owner_boundary_json();
GR_TOOLS_MODULE_MESHES_API const char* gr_tools_module_meshes_mesh_packet_schema_json();

}
