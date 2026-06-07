#pragma once

#include <cstddef>

namespace ghostrigger::phase15::ghostrigger_autorig {

using PythonFunctionDescriptorJson = const char* (*)();

struct PythonFunctionDescriptorEntry {
    const char* python_file;
    const char* qualname;
    const char* function_type;
    PythonFunctionDescriptorJson descriptor_json;
};

const char* src_autorig_accurig_guideplacer_place_guides_clamp_line_327_5bc55e06_descriptor_json();
const char* src_autorig_auto_rigger_rigextractor_extract_index_line_335_1c027174_descriptor_json();
const char* src_autorig_auto_rigger_rigextractor_extract_add_bone_line_360_fa66f26c_descriptor_json();
const char* src_autorig_auto_rigger_rigextractor_extract_walk_dummies_line_382_b4c5b65c_descriptor_json();
const char* src_autorig_auto_rigger_autorigger_bind_pose_from_fbx_bones_norm_line_872_52f30d34_descriptor_json();
const char* src_autorig_retarget_engine_meshscaler_apply_scale_node_line_493_fdfe78ca_descriptor_json();

const PythonFunctionDescriptorEntry* nestedfunctions_descriptors(std::size_t& count);

} // namespace ghostrigger::phase15::ghostrigger_autorig
