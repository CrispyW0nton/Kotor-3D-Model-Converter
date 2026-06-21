#pragma once

#if defined(_WIN32)
#if defined(GHOSTRIGGER_TOOLS_NODES_SKELETON_BROWSER_EXPORTS)
#define GR_TOOLS_NODES_SKELETON_BROWSER_API __declspec(dllexport)
#else
#define GR_TOOLS_NODES_SKELETON_BROWSER_API __declspec(dllimport)
#endif
#else
#define GR_TOOLS_NODES_SKELETON_BROWSER_API
#endif

extern "C" {

GR_TOOLS_NODES_SKELETON_BROWSER_API const char* gr_tools_nodes_skeleton_browser_version();
GR_TOOLS_NODES_SKELETON_BROWSER_API const char* gr_tools_nodes_skeleton_browser_capabilities_json();
GR_TOOLS_NODES_SKELETON_BROWSER_API const char* gr_tools_nodes_skeleton_browser_owner_boundary_json();
GR_TOOLS_NODES_SKELETON_BROWSER_API const char* gr_tools_nodes_skeleton_browser_node_tree_schema_json();

}
