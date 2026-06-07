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

const char* src_core_validation_viewport_validator_viewportvalidator_looks_like_ascii_mdl_line_58_29f4113d_descriptor_json();
const char* src_core_validation_viewport_validator_viewportvalidator_game_version_line_72_8a0a958f_descriptor_json();
const char* src_core_validation_viewport_validator_viewportvalidator_to_wxyz_line_245_84c4d9fa_descriptor_json();
const char* src_core_validation_viewport_validator_viewportvalidator_read_grayscale_line_283_29fcf5e8_descriptor_json();

const PythonFunctionDescriptorEntry* staticmethods_descriptors(std::size_t& count);

} // namespace ghostrigger::phase15::ghostrigger_validation
