#pragma once

#include <cstddef>

namespace ghostrigger::phase15::ghostrigger_level {

using PythonFunctionDescriptorJson = const char* (*)();

struct PythonFunctionDescriptorEntry {
    const char* python_file;
    const char* qualname;
    const char* function_type;
    PythonFunctionDescriptorJson descriptor_json;
};

const char* src_core_level_kmap_validator_kmapvalidator_valid_transform_line_123_f2f62e68_descriptor_json();
const char* src_core_level_level_export_bridge_levelexportbridge_single_export_model_line_106_74e418b1_descriptor_json();

const PythonFunctionDescriptorEntry* staticmethods_descriptors(std::size_t& count);

} // namespace ghostrigger::phase15::ghostrigger_level
