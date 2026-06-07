#include "GhostRiggerToolsContentBrowser.h"

namespace {

constexpr const char* kVersion = "0.1.0";
constexpr const char* kOwnerBoundary =
    R"({"schema":"tools_content_browser_owner_boundary.v1",)"
    R"("tool_package":"GhostRigger.Tools.ContentBrowser",)"
    R"("owner_surface":"Content Browser",)"
    R"("owner_package":"native/GhostRigger.Tools.ContentBrowser",)"
    R"("bridge_method":"C ABI DLL",)"
    R"("diagnostic_only":true,)"
    R"("cpp_owns":["catalogue_query_diagnostics","asset_index_packet_metadata","filter_sort_helper_contracts"],)"
    R"("python_owns":["content_browser_ui","resource_discovery_policy","game_semantics","selection_state","visible_workflow"],)"
    R"("native_index_enabled":false})";
constexpr const char* kCatalogueSchema =
    R"({"schema":"tools_content_browser_catalogue_schema.v1",)"
    R"("tool_package":"GhostRigger.Tools.ContentBrowser",)"
    R"("diagnostic_only":true,"native_index_enabled":false,)"
    R"("input_packets":["game_root","resource_scope","filter_terms","sort_mode"],)"
    R"("output_packets":["catalogue_rows","resource_type_counts","filter_diagnostics"],)"
    R"("query_attempted":false,"result_count":0,)"
    R"("failure_points":["game_root_missing","resource_scope_missing","native_index_disabled"]})";

} // namespace

extern "C" {

GR_TOOLS_CONTENT_BROWSER_API const char* gr_tools_content_browser_version() {
    return kVersion;
}

GR_TOOLS_CONTENT_BROWSER_API const char* gr_tools_content_browser_capabilities_json() {
    return R"({"name":"GhostRigger.Tools.ContentBrowser","version":"0.1.0",)"
           R"("phase":"P1 foundation","tool_package":true,)"
           R"("owner_surface":"Content Browser","bridge_method":"C ABI DLL",)"
           R"("diagnostic_only":true,"native_index_enabled":false,)"
           R"("capabilities":["owner_boundary","catalogue_schema","filter_sort_placeholder"],)"
           R"("python_fallback_required":true})";
}

GR_TOOLS_CONTENT_BROWSER_API const char* gr_tools_content_browser_owner_boundary_json() {
    return kOwnerBoundary;
}

GR_TOOLS_CONTENT_BROWSER_API const char* gr_tools_content_browser_catalogue_schema_json() {
    return kCatalogueSchema;
}

}
