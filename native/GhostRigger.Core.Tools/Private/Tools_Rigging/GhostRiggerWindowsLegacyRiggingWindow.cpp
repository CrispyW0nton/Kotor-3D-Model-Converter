#include "GhostRiggerPythonPayloadResource.h"
#include "Tools_Rigging/GhostRiggerWindowsLegacyRiggingWindow.h"

namespace {

constexpr const char* kVersion = "0.1.0";
constexpr const char* kOwnerBoundary =
    R"({"schema":"windows_legacy_rigging_window_owner_boundary.v1",)"
    R"("window_package":"GhostRigger.Core.Tools",)"
    R"("owner_surface":"Legacy Rigging Window",)"
    R"("owner_package":"native/GhostRigger.Core.Tools",)"
    R"("bridge_method":"C ABI DLL",)"
    R"("diagnostic_only":true,)"
    R"("cpp_owns":["legacy_rigging_host_service_metadata","native_command_routing_metadata","window_diagnostics"],)"
    R"("python_owns":["qt_widgets","legacy_rigging_workflow","docks","menus","themes","layouts","visible_window_state"],)"
    R"("native_shell_enabled":false})";
constexpr const char* kHostServiceSchema =
    R"({"schema":"windows_legacy_rigging_window_host_service_schema.v1",)"
    R"("window_package":"GhostRigger.Core.Tools",)"
    R"("diagnostic_only":true,"native_shell_enabled":false,)"
    R"("service_packets":["host_service_registry","native_command_route","window_diagnostic_record","startup_bridge_status"],)"
    R"("host_module_registered":false,"service_count":0,)"
    R"("visible_shell_mutation_allowed":false,)"
    R"("failure_points":["host_module_missing","python_window_owner_active","native_shell_disabled","service_registry_empty"]})";

} // namespace

extern "C" {

GR_WINDOWS_LEGACY_RIGGING_WINDOW_API const char* gr_windows_legacy_rigging_window_version() {
    return kVersion;
}

GR_WINDOWS_LEGACY_RIGGING_WINDOW_API const char* gr_windows_legacy_rigging_window_capabilities_json() {
    return R"({"name":"GhostRigger.Core.Tools","version":"0.1.0",)"
           R"("phase":"P1 foundation","window_package":true,)"
           R"("owner_surface":"Legacy Rigging Window","bridge_method":"C ABI DLL",)"
           R"("diagnostic_only":true,"native_shell_enabled":false,)"
           R"("capabilities":["owner_boundary","host_service_schema","window_diagnostics_placeholder"],)"
           R"("python_fallback_required":true})";
}

GR_WINDOWS_LEGACY_RIGGING_WINDOW_API const char* gr_windows_legacy_rigging_window_owner_boundary_json() {
    return kOwnerBoundary;
}

GR_WINDOWS_LEGACY_RIGGING_WINDOW_API const char* gr_windows_legacy_rigging_window_host_service_schema_json() {
    return kHostServiceSchema;
}

}

