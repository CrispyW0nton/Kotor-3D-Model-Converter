#include "GhostRiggerPythonPayloadResource.h"
#include "Tools_SceneInformation/GhostRiggerToolsSceneInformation.h"

namespace {

constexpr const char* kVersion = "0.1.0";
constexpr const char* kOwnerBoundary =
    R"({"schema":"tools_scene_information_owner_boundary.v1",)"
    R"("tool_package":"GhostRigger.Core.Tools",)"
    R"("owner_surface":"Scene Information",)"
    R"("owner_package":"native/GhostRigger.Core.Tools",)"
    R"("bridge_method":"C ABI DLL",)"
    R"("diagnostic_only":true,)"
    R"("cpp_owns":["scene_summary_packet_metadata","selection_statistics_contracts","viewport_diagnostic_counters"],)"
    R"("python_owns":["scene_information_ui","active_scene_lifetime","visible_workflow","project_dirty_state"],)"
    R"("native_scene_query_enabled":false})";
constexpr const char* kSceneSummarySchema =
    R"({"schema":"tools_scene_information_scene_summary_schema.v1",)"
    R"("tool_package":"GhostRigger.Core.Tools",)"
    R"("diagnostic_only":true,"native_scene_query_enabled":false,)"
    R"("input_packets":["scene_id","selection_ids","visible_filter","diagnostic_flags"],)"
    R"("output_packets":["object_counts","mesh_counts","material_counts","selection_summary"],)"
    R"("query_attempted":false,"result_count":0,)"
    R"("failure_points":["scene_handle_missing","scene_snapshot_missing","native_scene_query_disabled"]})";

} // namespace

extern "C" {

GR_TOOLS_SCENE_INFORMATION_API const char* gr_tools_scene_information_version() {
    return kVersion;
}

GR_TOOLS_SCENE_INFORMATION_API const char* gr_tools_scene_information_capabilities_json() {
    return R"({"name":"GhostRigger.Core.Tools","version":"0.1.0",)"
           R"("phase":"P1 foundation","tool_package":true,)"
           R"("owner_surface":"Scene Information","bridge_method":"C ABI DLL",)"
           R"("diagnostic_only":true,"native_scene_query_enabled":false,)"
           R"("capabilities":["owner_boundary","scene_summary_schema","selection_statistics_placeholder"],)"
           R"("python_fallback_required":true})";
}

GR_TOOLS_SCENE_INFORMATION_API const char* gr_tools_scene_information_owner_boundary_json() {
    return kOwnerBoundary;
}

GR_TOOLS_SCENE_INFORMATION_API const char* gr_tools_scene_information_scene_summary_schema_json() {
    return kSceneSummarySchema;
}

}

