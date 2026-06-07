#include "PythonFunctions/ClassMethods.h"

namespace ghostrigger::phase15::ghostrigger_lighting {

const char* src_core_lighting_light_model_ghostriggerlight_from_object_line_60_d4b090e4_descriptor_json() {
    return R"grjson({"schema":"ghostrigger.phase15.python_function_migration.v1","project":"GhostRigger.Lighting","python_module":"src.core.lighting.light_model","python_file":"src/core/lighting/light_model.py","qualname":"GhostRiggerLight.from_object","name":"from_object","kind":"class_methods","line":60,"end_line":91,"signature":{"args":["cls","obj","source_type"],"positional_count":2,"keyword_only_count":1,"has_vararg":false,"has_kwarg":false},"native_status":"migration_stub","python_fallback_required":true,"heavy_cpp_candidate":true})grjson";
}

const char* src_core_lighting_lightmap_bake_settings_lightmapbakesettings_for_quality_line_123_5a1517f1_descriptor_json() {
    return R"grjson({"schema":"ghostrigger.phase15.python_function_migration.v1","project":"GhostRigger.Lighting","python_module":"src.core.lighting.lightmap_bake_settings","python_file":"src/core/lighting/lightmap_bake_settings.py","qualname":"LightmapBakeSettings.for_quality","name":"for_quality","kind":"class_methods","line":123,"end_line":162,"signature":{"args":["cls","preset"],"positional_count":2,"keyword_only_count":0,"has_vararg":false,"has_kwarg":true},"native_status":"migration_stub","python_fallback_required":true,"heavy_cpp_candidate":true})grjson";
}

const char* src_core_lighting_particle_emitter_emitterconfig_from_node_line_218_43df53e1_descriptor_json() {
    return R"grjson({"schema":"ghostrigger.phase15.python_function_migration.v1","project":"GhostRigger.Lighting","python_module":"src.core.lighting.particle_emitter","python_file":"src/core/lighting/particle_emitter.py","qualname":"EmitterConfig.from_node","name":"from_node","kind":"class_methods","line":218,"end_line":255,"signature":{"args":["cls","node"],"positional_count":2,"keyword_only_count":0,"has_vararg":false,"has_kwarg":false},"native_status":"migration_stub","python_fallback_required":true,"heavy_cpp_candidate":true})grjson";
}

const PythonFunctionDescriptorEntry* classmethods_descriptors(std::size_t& count) {
    static const PythonFunctionDescriptorEntry entries[] = {
        {"src/core/lighting/light_model.py", "GhostRiggerLight.from_object", "class_methods", &src_core_lighting_light_model_ghostriggerlight_from_object_line_60_d4b090e4_descriptor_json},
        {"src/core/lighting/lightmap_bake_settings.py", "LightmapBakeSettings.for_quality", "class_methods", &src_core_lighting_lightmap_bake_settings_lightmapbakesettings_for_quality_line_123_5a1517f1_descriptor_json},
        {"src/core/lighting/particle_emitter.py", "EmitterConfig.from_node", "class_methods", &src_core_lighting_particle_emitter_emitterconfig_from_node_line_218_43df53e1_descriptor_json},
    };
    count = sizeof(entries) / sizeof(entries[0]);
    return entries;
}

} // namespace ghostrigger::phase15::ghostrigger_lighting
