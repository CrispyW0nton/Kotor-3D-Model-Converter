#include "GhostRiggerPythonPayloadResource.h"
#include "GhostRiggerWindowsLevelEditor.h"

namespace {

constexpr const char* kVersion = "0.1.0";
constexpr const char* kOwnerBoundary =
    R"({"schema":"windows_level_editor_owner_boundary.v1",)"
    R"("window_package":"GhostRigger.Windows.Editor.Level",)"
    R"("owner_surface":"Level Editor",)"
    R"("owner_package":"native/GhostRigger.Windows.Editor.Level",)"
    R"("bridge_method":"C ABI DLL",)"
    R"("diagnostic_only":true,)"
    R"("cpp_owns":["level_editor_host_service_metadata","native_command_routing_metadata","window_diagnostics"],)"
    R"("python_owns":["qt_widgets","level_editor_workflow","docks","menus","themes","layouts","visible_window_state"],)"
    R"("native_shell_enabled":false})";
constexpr const char* kHostServiceSchema =
    R"({"schema":"windows_level_editor_host_service_schema.v1",)"
    R"("window_package":"GhostRigger.Windows.Editor.Level",)"
    R"("diagnostic_only":true,"native_shell_enabled":false,)"
    R"("service_packets":["host_service_registry","native_command_route","window_diagnostic_record","startup_bridge_status"],)"
    R"("host_module_registered":false,"service_count":0,)"
    R"("visible_shell_mutation_allowed":false,)"
    R"("failure_points":["host_module_missing","python_window_owner_active","native_shell_disabled","service_registry_empty"]})";

} // namespace

extern "C" {

GR_WINDOWS_LEVEL_EDITOR_API const char* gr_windows_level_editor_version() {
    return kVersion;
}

GR_WINDOWS_LEVEL_EDITOR_API const char* gr_windows_level_editor_capabilities_json() {
    return R"({"name":"GhostRigger.Windows.Editor.Level","version":"0.1.0",)"
           R"("phase":"P1 foundation","window_package":true,)"
           R"("owner_surface":"Level Editor","bridge_method":"C ABI DLL",)"
           R"("diagnostic_only":true,"native_shell_enabled":false,)"
           R"("capabilities":["owner_boundary","host_service_schema","window_diagnostics_placeholder"],)"
           R"("python_fallback_required":true})";
}

GR_WINDOWS_LEVEL_EDITOR_API const char* gr_windows_level_editor_owner_boundary_json() {
    return kOwnerBoundary;
}

GR_WINDOWS_LEVEL_EDITOR_API const char* gr_windows_level_editor_host_service_schema_json() {
    return kHostServiceSchema;
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
