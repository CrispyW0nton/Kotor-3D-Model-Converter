#pragma once

#include <cstddef>

namespace ghostrigger::phase15::ghostrigger_systems_bas {

using PythonFunctionDescriptorJson = const char* (*)();

struct PythonFunctionDescriptorEntry {
    const char* python_file;
    const char* qualname;
    const char* function_type;
    PythonFunctionDescriptorJson descriptor_json;
};

const char* src_systems_bas_attachment_alignment_normalize_bas_transform_values_line_38_bdcb89bd_descriptor_json();
const char* src_systems_bas_model_recipe_normalize_bas_layer_transform_values_line_162_3ef7d12a_descriptor_json();

const PythonFunctionDescriptorEntry* nestedfunctions_descriptors(std::size_t& count);

} // namespace ghostrigger::phase15::ghostrigger_systems_bas
