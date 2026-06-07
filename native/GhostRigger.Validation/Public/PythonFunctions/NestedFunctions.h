#pragma once

#include <cstddef>

namespace ghostrigger::phase15::ghostrigger_validation {

using PythonFunctionDescriptorJson = const char* (*)();

struct PythonFunctionDescriptorEntry {
    const char* python_file;
    const char* qualname;
    const char* function_type;
    PythonFunctionDescriptorJson descriptor_json;
};

const char* src_core_validation_animation_block_validator_validate_raw_animation_footprint_walk_line_148_d39479ce_descriptor_json();
const char* src_core_validation_validation_bus_validationbus_subscribe_unsubscribe_line_158_b8f03986_descriptor_json();

const PythonFunctionDescriptorEntry* nestedfunctions_descriptors(std::size_t& count);

} // namespace ghostrigger::phase15::ghostrigger_validation
