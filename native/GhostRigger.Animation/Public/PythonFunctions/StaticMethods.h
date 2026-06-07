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

const char* src_core_animation_animation_library_animationretargeter_build_map_line_372_debf3019_descriptor_json();
const char* src_core_animation_animation_library_animationretargeter_from_json_line_391_cc3025a4_descriptor_json();
const char* src_core_animation_animation_library_animationretargeter_save_json_line_398_0daaa362_descriptor_json();
const char* src_core_animation_gpu_skinning_matrixpaletteuploader_qbone_inverse_bind_matrix_line_738_39b95042_descriptor_json();
const char* src_core_animation_gpu_skinning_matrixpaletteuploader_qbone_direct_bind_matrix_line_757_49040c9a_descriptor_json();
const char* src_core_animation_gpu_skinning_matrixpaletteuploader_qbone_inverse_bind_matrix_g5_line_779_8029ac58_descriptor_json();

const PythonFunctionDescriptorEntry* staticmethods_descriptors(std::size_t& count);

} // namespace ghostrigger::phase15::ghostrigger_animation
