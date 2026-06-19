#include "GhostRiggerPythonPayloadResource.h"
#include "GhostRiggerToolsResourceBrowser.h"

namespace {

constexpr const char* kVersion = "0.1.0";
constexpr const char* kOwnerBoundary =
    R"({"schema":"tools_resource_browser_owner_boundary.v1","tool_package":"GhostRigger.Core.Tools.ResourceBrowser",)"
    R"("owner_surface":"Resource Browser","owner_package":"native/GhostRigger.Core.Tools.ResourceBrowser",)"
    R"("bridge_method":"C ABI DLL","diagnostic_only":true,)"
    R"("cpp_owns":["resource_catalogue_diagnostics","resource_row_packet_metadata","filter_helper_contracts"],)"
    R"("python_owns":["resource_discovery_policy","game_semantics","selection_state","preview_workflow","visible_workflow"],)"
    R"("native_index_enabled":false})";
constexpr const char* kCatalogueSchema =
    R"({"schema":"tools_resource_browser_catalogue_schema.v1","tool_package":"GhostRigger.Core.Tools.ResourceBrowser",)"
    R"("diagnostic_only":true,"native_index_enabled":false,)"
    R"("input_packets":["game_root","resource_types","filter_terms","selection_scope"],)"
    R"("output_packets":["resource_rows","resource_type_counts","preview_readiness"],)"
    R"("query_attempted":false,"result_count":0,)"
    R"("failure_points":["game_root_missing","resource_types_missing","native_index_disabled"]})";

} // namespace

extern "C" {

GR_TOOLS_RESOURCE_BROWSER_API const char* gr_tools_resource_browser_version() {
    return kVersion;
}

GR_TOOLS_RESOURCE_BROWSER_API const char* gr_tools_resource_browser_capabilities_json() {
    return R"({"name":"GhostRigger.Core.Tools.ResourceBrowser","version":"0.1.0","phase":"P1 foundation",)"
           R"("tool_package":true,"owner_surface":"Resource Browser","bridge_method":"C ABI DLL",)"
           R"("diagnostic_only":true,"native_index_enabled":false,)"
           R"("capabilities":["owner_boundary","catalogue_schema","resource_filter_placeholder"],)"
           R"("python_fallback_required":true})";
}

GR_TOOLS_RESOURCE_BROWSER_API const char* gr_tools_resource_browser_owner_boundary_json() {
    return kOwnerBoundary;
}

GR_TOOLS_RESOURCE_BROWSER_API const char* gr_tools_resource_browser_catalogue_schema_json() {
    return kCatalogueSchema;
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
