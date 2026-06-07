#pragma once

#include <cstddef>

namespace ghostrigger::phase15::ghostrigger_game {

using PythonFunctionDescriptorJson = const char* (*)();

struct PythonFunctionDescriptorEntry {
    const char* python_file;
    const char* qualname;
    const char* function_type;
    PythonFunctionDescriptorJson descriptor_json;
};

const char* src_core_game_kotor_loader_read_mesh_safe_vec3_list_line_776_3a830960_descriptor_json();
const char* src_core_game_kotor_loader_read_mesh_safe_vec2_list_line_784_a5cd70ac_descriptor_json();
const char* src_core_game_kotor_loader_read_mesh_safe_float_line_809_85bd8cf1_descriptor_json();
const char* src_core_game_kotor_loader_read_mesh_safe_uv_line_815_aa513aa1_descriptor_json();
const char* src_core_game_pykotor_mdl_io_fix_ghostrigger_trimesh_read_read_i32_as_u32_line_367_d948baad_descriptor_json();

const PythonFunctionDescriptorEntry* nestedfunctions_descriptors(std::size_t& count);

} // namespace ghostrigger::phase15::ghostrigger_game
