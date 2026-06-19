#include "GhostRiggerPythonPayloadResource.h"
#include "GhostRiggerToolsTwoDABrowser.h"

namespace {

constexpr const char* kVersion = "0.1.0";
constexpr const char* kOwnerBoundary =
    R"({"schema":"tools_two_da_browser_owner_boundary.v1","tool_package":"GhostRigger.Core.Tools.TwoDABrowser",)"
    R"("owner_surface":"2DA Browser","owner_package":"native/GhostRigger.Core.Tools.TwoDABrowser",)"
    R"("bridge_method":"C ABI DLL","diagnostic_only":true,)"
    R"("cpp_owns":["two_da_table_query_diagnostics","row_column_packet_metadata","filter_helper_contracts"],)"
    R"("python_owns":["two_da_parsing_policy","game_semantics","editing_workflow","selection_state","visible_ui"],)"
    R"("native_table_query_enabled":false})";
constexpr const char* kTableSchema =
    R"({"schema":"tools_two_da_browser_table_schema.v1","tool_package":"GhostRigger.Core.Tools.TwoDABrowser",)"
    R"("diagnostic_only":true,"native_table_query_enabled":false,)"
    R"("input_packets":["table_resref","resource_scope","column_filter","row_filter"],)"
    R"("output_packets":["table_rows","column_metadata","filter_diagnostics"],)"
    R"("query_attempted":false,"result_count":0,)"
    R"("failure_points":["table_resref_missing","resource_scope_missing","native_table_query_disabled"]})";

} // namespace

extern "C" {

GR_TOOLS_TWO_DA_BROWSER_API const char* gr_tools_two_da_browser_version() {
    return kVersion;
}

GR_TOOLS_TWO_DA_BROWSER_API const char* gr_tools_two_da_browser_capabilities_json() {
    return R"({"name":"GhostRigger.Core.Tools.TwoDABrowser","version":"0.1.0","phase":"P1 foundation",)"
           R"("tool_package":true,"owner_surface":"2DA Browser","bridge_method":"C ABI DLL",)"
           R"("diagnostic_only":true,"native_table_query_enabled":false,)"
           R"("capabilities":["owner_boundary","table_schema","row_column_filter_placeholder"],)"
           R"("python_fallback_required":true})";
}

GR_TOOLS_TWO_DA_BROWSER_API const char* gr_tools_two_da_browser_owner_boundary_json() {
    return kOwnerBoundary;
}

GR_TOOLS_TWO_DA_BROWSER_API const char* gr_tools_two_da_browser_table_schema_json() {
    return kTableSchema;
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
