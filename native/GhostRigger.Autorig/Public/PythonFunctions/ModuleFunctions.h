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

const char* src_autorig_auto_rigger_bone_colour_line_122_56b926ee_descriptor_json();
const char* src_autorig_auto_rigger_build_skeleton_line_131_e387f022_descriptor_json();
const char* src_autorig_auto_rigger_normalize_skeleton_to_kotor_line_892_8276a0b5_descriptor_json();
const char* src_autorig_auto_rigger_get_bone_colour_map_line_902_0a076be0_descriptor_json();
const char* src_autorig_cloth_rig_model_data_line_76_db8ee615_descriptor_json();
const char* src_autorig_cloth_rig_run_cloth_preset_dialog_line_811_8343f8b1_descriptor_json();
const char* src_autorig_cloth_rig_confirm_cloth_action_line_823_871d4649_descriptor_json();
const char* src_autorig_retarget_engine_export_as_mdl_line_1396_38ae9fad_descriptor_json();

const PythonFunctionDescriptorEntry* modulefunctions_descriptors(std::size_t& count);

} // namespace ghostrigger::phase15::ghostrigger_autorig
