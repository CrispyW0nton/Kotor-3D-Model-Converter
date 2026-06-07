#pragma once

#include <cstddef>

namespace ghostrigger::phase15::ghostrigger_assets {

using PythonFunctionDescriptorJson = const char* (*)();

struct PythonFunctionDescriptorEntry {
    const char* python_file;
    const char* qualname;
    const char* function_type;
    PythonFunctionDescriptorJson descriptor_json;
};

const char* src_core_assets_override_layer_overridelayer_game_dir_line_112_49db4eaa_descriptor_json();
const char* src_core_assets_override_layer_overridelayer_override_dir_line_116_d702c23f_descriptor_json();
const char* src_core_assets_override_layer_overridelayer_is_available_line_120_4fde95ac_descriptor_json();
const char* src_core_assets_override_layer_overridelayer_entry_count_line_125_b6182ba0_descriptor_json();

const PythonFunctionDescriptorEntry* properties_descriptors(std::size_t& count);

} // namespace ghostrigger::phase15::ghostrigger_assets
