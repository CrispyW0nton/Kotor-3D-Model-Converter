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

const char* src_core_level_kmap_model_utc_now_iso_line_19_f20cd66e_descriptor_json();
const char* src_core_level_kmap_model_stable_id_line_23_5bbc0cf4_descriptor_json();
const char* src_core_level_kmap_model_vec3_line_27_72d6d689_descriptor_json();
const char* src_core_level_kmap_model_dict_line_38_e0df7116_descriptor_json();
const char* src_core_level_kmap_model_new_kmap_project_line_359_3fc4d07f_descriptor_json();
const char* src_core_level_level_manifest_build_level_manifest_line_12_f6f49199_descriptor_json();

const PythonFunctionDescriptorEntry* modulefunctions_descriptors(std::size_t& count);

} // namespace ghostrigger::phase15::ghostrigger_level
