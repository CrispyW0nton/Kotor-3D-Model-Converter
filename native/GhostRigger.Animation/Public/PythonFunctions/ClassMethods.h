#pragma once

#include <cstddef>

namespace ghostrigger::phase15::ghostrigger_animation {

using PythonFunctionDescriptorJson = const char* (*)();

struct PythonFunctionDescriptorEntry {
    const char* python_file;
    const char* qualname;
    const char* function_type;
    PythonFunctionDescriptorJson descriptor_json;
};

const char* src_core_animation_animation_engine_supermodelresolver_configure_line_82_459ed917_descriptor_json();
const char* src_core_animation_animation_engine_supermodelresolver_clear_cache_line_90_c728b5dd_descriptor_json();
const char* src_core_animation_animation_engine_supermodelresolver_prime_cache_line_95_33fc357d_descriptor_json();
const char* src_core_animation_animation_engine_supermodelresolver_cache_game_key_line_100_303a5917_descriptor_json();
const char* src_core_animation_animation_engine_supermodelresolver_is_null_ref_line_113_a62f019d_descriptor_json();
const char* src_core_animation_animation_engine_supermodelresolver_load_supermodel_line_119_5f17088c_descriptor_json();
const char* src_core_animation_animation_engine_supermodelresolver_resolve_animation_line_165_2e13983f_descriptor_json();
const char* src_core_animation_animation_engine_supermodelresolver_list_all_animations_line_225_a894df0f_descriptor_json();
const char* src_core_animation_animation_engine_supermodelresolver_animation_source_type_line_269_e16b380b_descriptor_json();

const PythonFunctionDescriptorEntry* classmethods_descriptors(std::size_t& count);

} // namespace ghostrigger::phase15::ghostrigger_animation
