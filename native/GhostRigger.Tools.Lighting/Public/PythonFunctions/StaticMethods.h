#pragma once

#include <cstddef>

namespace ghostrigger::phase15::ghostrigger_tools_lighting {

using PythonFunctionDescriptorJson = const char* (*)();

struct PythonFunctionDescriptorEntry {
    const char* python_file;
    const char* qualname;
    const char* function_type;
    PythonFunctionDescriptorJson descriptor_json;
};

const char* src_core_lighting_aurora_light_adapter_auroralightadapter_is_aurora_light_line_32_72871b3e_descriptor_json();
const char* src_core_lighting_lighting_rig_presets_lightingrigpresets_create_line_10_24da2ddb_descriptor_json();

const PythonFunctionDescriptorEntry* staticmethods_descriptors(std::size_t& count);

} // namespace ghostrigger::phase15::ghostrigger_tools_lighting
