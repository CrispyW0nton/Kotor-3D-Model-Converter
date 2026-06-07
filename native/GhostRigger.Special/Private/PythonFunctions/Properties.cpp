#include "PythonFunctions/Properties.h"

namespace ghostrigger::phase15::ghostrigger_special {

const char* src_core_special_unity_malak_smoke_unitybridgeclient_endpoint_line_34_0219d326_descriptor_json() {
    return R"grjson({"schema":"ghostrigger.phase15.python_function_migration.v1","project":"GhostRigger.Special","python_module":"src.core.special.unity_malak_smoke","python_file":"src/core/special/unity_malak_smoke.py","qualname":"UnityBridgeClient.endpoint","name":"endpoint","kind":"properties","line":34,"end_line":35,"signature":{"args":["self"],"positional_count":1,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_status":"migration_stub","python_fallback_required":true,"heavy_cpp_candidate":false})grjson";
}

const PythonFunctionDescriptorEntry* properties_descriptors(std::size_t& count) {
    static const PythonFunctionDescriptorEntry entries[] = {
        {"src/core/special/unity_malak_smoke.py", "UnityBridgeClient.endpoint", "properties", &src_core_special_unity_malak_smoke_unitybridgeclient_endpoint_line_34_0219d326_descriptor_json},
    };
    count = sizeof(entries) / sizeof(entries[0]);
    return entries;
}

} // namespace ghostrigger::phase15::ghostrigger_special
