#include "PythonFunctions/StaticMethods.h"

namespace ghostrigger::phase15::ghostrigger_lighting {

const char* src_core_lighting_aurora_light_adapter_auroralightadapter_is_aurora_light_line_32_72871b3e_descriptor_json() {
    return R"grjson({"schema":"ghostrigger.phase15.python_function_migration.v1","project":"GhostRigger.Lighting","python_module":"src.core.lighting.aurora_light_adapter","python_file":"src/core/lighting/aurora_light_adapter.py","qualname":"AuroraLightAdapter.is_aurora_light","name":"is_aurora_light","kind":"static_methods","line":32,"end_line":35,"signature":{"args":["record"],"positional_count":1,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_status":"migration_stub","python_fallback_required":true,"heavy_cpp_candidate":true})grjson";
}

const char* src_core_lighting_lighting_rig_presets_lightingrigpresets_create_line_10_24da2ddb_descriptor_json() {
    return R"grjson({"schema":"ghostrigger.phase15.python_function_migration.v1","project":"GhostRigger.Lighting","python_module":"src.core.lighting.lighting_rig_presets","python_file":"src/core/lighting/lighting_rig_presets.py","qualname":"LightingRigPresets.create","name":"create","kind":"static_methods","line":10,"end_line":67,"signature":{"args":["preset"],"positional_count":1,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_status":"migration_stub","python_fallback_required":true,"heavy_cpp_candidate":true})grjson";
}

const PythonFunctionDescriptorEntry* staticmethods_descriptors(std::size_t& count) {
    static const PythonFunctionDescriptorEntry entries[] = {
        {"src/core/lighting/aurora_light_adapter.py", "AuroraLightAdapter.is_aurora_light", "static_methods", &src_core_lighting_aurora_light_adapter_auroralightadapter_is_aurora_light_line_32_72871b3e_descriptor_json},
        {"src/core/lighting/lighting_rig_presets.py", "LightingRigPresets.create", "static_methods", &src_core_lighting_lighting_rig_presets_lightingrigpresets_create_line_10_24da2ddb_descriptor_json},
    };
    count = sizeof(entries) / sizeof(entries[0]);
    return entries;
}

} // namespace ghostrigger::phase15::ghostrigger_lighting
