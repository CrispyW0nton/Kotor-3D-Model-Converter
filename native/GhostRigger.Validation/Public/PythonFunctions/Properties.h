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

const char* src_core_validation_animation_block_validator_rawanimationfootprintreport_node_names_line_108_8ae23bc4_descriptor_json();
const char* src_core_validation_validation_bus_validationreport_has_blocking_line_85_2f48161f_descriptor_json();
const char* src_core_validation_validation_bus_validationreport_has_errors_line_89_1b4a9e00_descriptor_json();
const char* src_core_validation_validation_bus_validationreport_blocking_issues_line_93_dd1bb43c_descriptor_json();

const PythonFunctionDescriptorEntry* properties_descriptors(std::size_t& count);

} // namespace ghostrigger::phase15::ghostrigger_validation
