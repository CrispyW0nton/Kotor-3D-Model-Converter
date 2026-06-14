#include "GhostRiggerPythonPayloadResource.h"
#include "GhostRiggerMeshTools.h"

namespace {

constexpr const char* kVersion = "0.1.0";
constexpr const char* kOwnerBoundary =
    R"({"schema":"mesh_tools_owner_boundary.v1",)"
    R"("module_package":"GhostRigger.Domain.Core.MeshTools",)"
    R"("source_package":"src/mesh_tools",)"
    R"("owner_surface":"Mesh editing tools",)"
    R"("owner_package":"native/GhostRigger.Domain.Core.MeshTools",)"
    R"("bridge_method":"C ABI DLL",)"
    R"("diagnostic_only":true,)"
    R"("cpp_owns":["module_boundary_metadata","dependency_scan_metadata","native_readiness_diagnostics"],)"
    R"("python_owns":["current_implementation","object_lifetime","workflow_policy","ui_state","runtime_behavior"],)"
    R"("native_implementation_enabled":false})";
constexpr const char* kDependencySchema =
    R"({"schema":"mesh_tools_dependency_schema.v1",)"
    R"("module_package":"GhostRigger.Domain.Core.MeshTools",)"
    R"("source_package":"src/mesh_tools",)"
    R"("diagnostic_only":true,)"
    R"("dependency_scan_complete":true,)"
    R"("native_dependencies_declared":[],)"
    R"("python_owner_active":true,)"
    R"("native_implementation_enabled":false})";
constexpr const char* kCommandSchema =
    R"({"schema":"mesh_tools_command_schema.v1",)"
    R"("module_package":"GhostRigger.Domain.Core.MeshTools",)"
    R"("owner_package":"native/GhostRigger.Domain.Core.MeshTools",)"
    R"("source_package":"src/mesh_tools",)"
    R"("native_command_contract_enabled":true,)"
    R"("runtime_bridge":"ipc:mesh_tool_command",)"
    R"("selection_modes":["object","vertex","edge","border","face","polygon","element"],)"
    R"("selection_commands":["status","set_mode","select_all","clear_selection","invert_selection","grow","shrink","loop","ring","convert_to_vertex","convert_to_edge","convert_to_border","convert_to_face","convert_to_polygon","convert_to_element"],)"
    R"("geometry_operations":["attach","detach","weld","target_weld","bridge","connect","cap","delete","remove_isolated","flip_normals","recalculate_normals"],)"
    R"("packet_keys":["command","mode","operation","options"],)"
    R"("result_keys":["ok","command","mode","active_mesh","counts","message","warnings","errors"],)"
    R"("requires_visible_app":true})";

} // namespace

extern "C" {

GHOSTRIGGER_MESH_TOOLS_API const char* gr_mesh_tools_version() {
    return kVersion;
}

GHOSTRIGGER_MESH_TOOLS_API const char* gr_mesh_tools_capabilities_json() {
    return R"({"name":"GhostRigger.Domain.Core.MeshTools","version":"0.1.0",)"
           R"("phase":"P1 module sweep","module_package":true,)"
           R"("source_package":"src/mesh_tools",)"
           R"("owner_surface":"Mesh editing tools","bridge_method":"C ABI DLL",)"
           R"("diagnostic_only":true,"native_implementation_enabled":false,)"
           R"("native_command_contract_enabled":true,)"
           R"("capabilities":["owner_boundary","dependency_schema","native_readiness_diagnostics","mesh_tool_command_schema"],)"
           R"("python_fallback_required":true})";
}

GHOSTRIGGER_MESH_TOOLS_API const char* gr_mesh_tools_owner_boundary_json() {
    return kOwnerBoundary;
}

GHOSTRIGGER_MESH_TOOLS_API const char* gr_mesh_tools_dependency_schema_json() {
    return kDependencySchema;
}

GHOSTRIGGER_MESH_TOOLS_API const char* gr_mesh_tools_command_schema_json() {
    return kCommandSchema;
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
