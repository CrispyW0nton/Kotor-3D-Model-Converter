#pragma once

#include <cstddef>

namespace ghostrigger::phase15::ghostrigger_lighting {

using PythonFunctionDescriptorJson = const char* (*)();

struct PythonFunctionDescriptorEntry {
    const char* python_file;
    const char* qualname;
    const char* function_type;
    PythonFunctionDescriptorJson descriptor_json;
};

const char* src_core_lighting_light_model_ghostriggerlight_from_object_line_60_d4b090e4_descriptor_json();
const char* src_core_lighting_lightmap_bake_settings_lightmapbakesettings_for_quality_line_123_5a1517f1_descriptor_json();
const char* src_core_lighting_particle_emitter_emitterconfig_from_node_line_218_43df53e1_descriptor_json();

const PythonFunctionDescriptorEntry* classmethods_descriptors(std::size_t& count);

} // namespace ghostrigger::phase15::ghostrigger_lighting
