#include "PythonFunctions/Properties.h"

namespace ghostrigger::phase15::ghostrigger_kotormcp {

const char* src_kotormcp_tools_debug_skinning_debugsession_uptime_s_line_119_caf797cb_descriptor_json() {
    return R"grjson({"schema":"ghostrigger.phase15.python_function_migration.v1","project":"GhostRigger.KotorMCP","python_module":"src.kotormcp.tools.debug_skinning","python_file":"src/kotormcp/tools/debug_skinning.py","qualname":"_DebugSession.uptime_s","name":"uptime_s","kind":"properties","line":119,"end_line":122,"signature":{"args":["self"],"positional_count":1,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_status":"migration_stub","python_fallback_required":true,"heavy_cpp_candidate":false})grjson";
}

const char* src_kotormcp_tools_discovery_resourceentryproxy_data_line_180_7da55bff_descriptor_json() {
    return R"grjson({"schema":"ghostrigger.phase15.python_function_migration.v1","project":"GhostRigger.KotorMCP","python_module":"src.kotormcp.tools.discovery","python_file":"src/kotormcp/tools/discovery.py","qualname":"_ResourceEntryProxy.data","name":"data","kind":"properties","line":180,"end_line":181,"signature":{"args":["self"],"positional_count":1,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_status":"migration_stub","python_fallback_required":true,"heavy_cpp_candidate":false})grjson";
}

const PythonFunctionDescriptorEntry* properties_descriptors(std::size_t& count) {
    static const PythonFunctionDescriptorEntry entries[] = {
        {"src/kotormcp/tools/debug_skinning.py", "_DebugSession.uptime_s", "properties", &src_kotormcp_tools_debug_skinning_debugsession_uptime_s_line_119_caf797cb_descriptor_json},
        {"src/kotormcp/tools/discovery.py", "_ResourceEntryProxy.data", "properties", &src_kotormcp_tools_discovery_resourceentryproxy_data_line_180_7da55bff_descriptor_json},
    };
    count = sizeof(entries) / sizeof(entries[0]);
    return entries;
}

} // namespace ghostrigger::phase15::ghostrigger_kotormcp
