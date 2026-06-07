#pragma once

#include <cstddef>

namespace ghostrigger::phase15::ghostrigger_kotormcp {

using PythonFunctionDescriptorJson = const char* (*)();

struct PythonFunctionDescriptorEntry {
    const char* python_file;
    const char* qualname;
    const char* function_type;
    PythonFunctionDescriptorJson descriptor_json;
};

const char* src_kotormcp_schemas_init_basemodel_model_validate_line_23_d78d3b93_descriptor_json();

const PythonFunctionDescriptorEntry* classmethods_descriptors(std::size_t& count);

} // namespace ghostrigger::phase15::ghostrigger_kotormcp
