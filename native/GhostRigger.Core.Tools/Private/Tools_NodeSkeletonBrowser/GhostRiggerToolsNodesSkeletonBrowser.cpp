#include "GhostRiggerPythonPayloadResource.h"
#include "Tools_NodeSkeletonBrowser/GhostRiggerToolsNodesSkeletonBrowser.h"

namespace {

constexpr const char* kVersion = "0.1.0";
constexpr const char* kOwnerBoundary =
    R"({"schema":"tools_nodes_skeleton_browser_owner_boundary.v1",)"
    R"("tool_package":"GhostRigger.Core.Tools",)"
    R"("owner_surface":"Nodes/Skeleton Browser",)"
    R"("owner_package":"native/GhostRigger.Core.Tools",)"
    R"("bridge_method":"C ABI DLL",)"
    R"("diagnostic_only":true,)"
    R"("cpp_owns":["node_tree_packet_metadata","skeleton_role_contracts","hierarchy_diagnostics"],)"
    R"("python_owns":["nodes_skeleton_browser_ui","node_selection_state","role_classification_policy","visible_workflow"],)"
    R"("native_node_tree_query_enabled":false})";
constexpr const char* kNodeTreeSchema =
    R"({"schema":"tools_nodes_skeleton_browser_node_tree_schema.v1",)"
    R"("tool_package":"GhostRigger.Core.Tools",)"
    R"("diagnostic_only":true,"native_node_tree_query_enabled":false,)"
    R"("input_packets":["model_handle","role_filters","selection_ids","hierarchy_flags"],)"
    R"("output_packets":["node_rows","role_counts","selection_summary","validation_messages"],)"
    R"("query_attempted":false,"result_count":0,)"
    R"("failure_points":["model_handle_missing","hierarchy_snapshot_missing","native_node_tree_query_disabled"]})";

} // namespace

extern "C" {

GR_TOOLS_NODES_SKELETON_BROWSER_API const char* gr_tools_nodes_skeleton_browser_version() {
    return kVersion;
}

GR_TOOLS_NODES_SKELETON_BROWSER_API const char* gr_tools_nodes_skeleton_browser_capabilities_json() {
    return R"({"name":"GhostRigger.Core.Tools","version":"0.1.0",)"
           R"("phase":"P1 foundation","tool_package":true,)"
           R"("owner_surface":"Nodes/Skeleton Browser","bridge_method":"C ABI DLL",)"
           R"("diagnostic_only":true,"native_node_tree_query_enabled":false,)"
           R"("capabilities":["owner_boundary","node_tree_schema","skeleton_role_placeholder"],)"
           R"("python_fallback_required":true})";
}

GR_TOOLS_NODES_SKELETON_BROWSER_API const char* gr_tools_nodes_skeleton_browser_owner_boundary_json() {
    return kOwnerBoundary;
}

GR_TOOLS_NODES_SKELETON_BROWSER_API const char* gr_tools_nodes_skeleton_browser_node_tree_schema_json() {
    return kNodeTreeSchema;
}

}

extern "C" {

__declspec(dllexport) const char* gr_python_payload_manifest_json() {
    return ghostrigger::native::core::payload::manifest_json_from_module_symbol(
        reinterpret_cast<const void*>(&gr_python_payload_manifest_json)
    );
}

__declspec(dllexport) unsigned int gr_python_payload_file_count() {
    return ghostrigger::native::core::payload::file_count_from_manifest_json(gr_python_payload_manifest_json());
}

}
