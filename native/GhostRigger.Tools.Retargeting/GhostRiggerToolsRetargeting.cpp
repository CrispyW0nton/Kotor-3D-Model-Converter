#include "../GhostRigger.Native.NativeCore/GhostRiggerPythonPayloadResource.h"
#include "GhostRiggerToolsRetargeting.h"

namespace {

constexpr const char* kVersion = "0.1.0";
constexpr const char* kOwnerBoundary =
    R"({"schema":"tools_retargeting_owner_boundary.v1",)"
    R"("tool_package":"GhostRigger.Tools.Retargeting",)"
    R"("owner_surface":"Retarget Workbench",)"
    R"("owner_package":"native/GhostRigger.Tools.Retargeting",)"
    R"("bridge_method":"C ABI DLL",)"
    R"("diagnostic_only":true,)"
    R"("cpp_owns":["pose_palette_blending_helpers","numeric_retarget_solve_packets","solver_diagnostics","batch_validation_helpers"],)"
    R"("python_owns":["animation_source_selection","ui_state","user_workflow","export_policy","project_session_persistence","mcp_truth_checks"],)"
    R"("native_solve_enabled":false})";
constexpr const char* kSolvePacketSchema =
    R"({"schema":"tools_retargeting_solve_packet_schema.v1",)"
    R"("tool_package":"GhostRigger.Tools.Retargeting",)"
    R"("diagnostic_only":true,)"
    R"("native_solve_enabled":false,)"
    R"("input_packets":["source_skeleton_handle","target_skeleton_handle","source_animation_handle","retarget_options"],)"
    R"("output_packets":["pose_palette_weights","bone_mapping_diagnostics","solver_error_metrics"],)"
    R"("solve_attempted":false,"solve_result_count":0,)"
    R"("failure_points":["source_skeleton_missing","target_skeleton_missing","animation_missing","native_solver_disabled"]})";

} // namespace

extern "C" {

GR_TOOLS_RETARGETING_API const char* gr_tools_retargeting_version() {
    return kVersion;
}

GR_TOOLS_RETARGETING_API const char* gr_tools_retargeting_capabilities_json() {
    return R"({"name":"GhostRigger.Tools.Retargeting","version":"0.1.0",)"
           R"("phase":"P1 foundation","tool_package":true,)"
           R"("owner_surface":"Retarget Workbench",)"
           R"("bridge_method":"C ABI DLL",)"
           R"("diagnostic_only":true,"native_solve_enabled":false,)"
           R"("capabilities":["owner_boundary","solve_packet_schema","solver_diagnostics_placeholder"],)"
           R"("python_fallback_required":true})";
}

GR_TOOLS_RETARGETING_API const char* gr_tools_retargeting_owner_boundary_json() {
    return kOwnerBoundary;
}

GR_TOOLS_RETARGETING_API const char* gr_tools_retargeting_solve_packet_schema_json() {
    return kSolvePacketSchema;
}

}

extern "C" {

__declspec(dllexport) const char* gr_python_payload_manifest_json() {
    return ghostrigger::native_payload::manifest_json_from_module_symbol(
        reinterpret_cast<const void*>(&gr_python_payload_manifest_json)
    );
}

__declspec(dllexport) unsigned int gr_python_payload_file_count() {
    return ghostrigger::native_payload::file_count_from_manifest_json(gr_python_payload_manifest_json());
}

}
