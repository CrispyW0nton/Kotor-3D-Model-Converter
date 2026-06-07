#include "PythonFunctions/ModuleFunctions.h"

namespace ghostrigger::phase15::ghostrigger_infra {

const char* src_infra_mcp_autostart_maybe_autostart_kotormcp_line_17_3a73802a_descriptor_json() {
    return R"grjson({"schema":"ghostrigger.phase15.python_function_migration.v1","project":"GhostRigger.Infra","python_module":"src.infra.mcp_autostart","python_file":"src/infra/mcp_autostart.py","qualname":"maybe_autostart_kotormcp","name":"maybe_autostart_kotormcp","kind":"module_functions","line":17,"end_line":90,"signature":{"args":[],"positional_count":0,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_status":"migration_stub","python_fallback_required":true,"heavy_cpp_candidate":true})grjson";
}

const PythonFunctionDescriptorEntry* modulefunctions_descriptors(std::size_t& count) {
    static const PythonFunctionDescriptorEntry entries[] = {
        {"src/infra/mcp_autostart.py", "maybe_autostart_kotormcp", "module_functions", &src_infra_mcp_autostart_maybe_autostart_kotormcp_line_17_3a73802a_descriptor_json},
    };
    count = sizeof(entries) / sizeof(entries[0]);
    return entries;
}

} // namespace ghostrigger::phase15::ghostrigger_infra
