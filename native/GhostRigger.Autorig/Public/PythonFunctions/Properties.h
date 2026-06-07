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

const char* src_autorig_accurig_bonemask_masked_bones_line_449_93e3b08c_descriptor_json();
const char* src_autorig_auto_rigger_rigtemplate_bone_names_line_200_c6130ec1_descriptor_json();
const char* src_autorig_cloth_rig_clothrigconfig_pin_mdl_line_119_9ea858a9_descriptor_json();
const char* src_autorig_cloth_rig_clothrigconfig_free_mdl_line_124_18b4397d_descriptor_json();
const char* src_autorig_retarget_engine_retargetengine_stage_line_618_11405e42_descriptor_json();
const char* src_autorig_retarget_engine_retargetengine_working_model_line_622_fd6f944a_descriptor_json();
const char* src_autorig_retarget_engine_retargetengine_reference_model_line_626_13816cbc_descriptor_json();

const PythonFunctionDescriptorEntry* properties_descriptors(std::size_t& count);

} // namespace ghostrigger::phase15::ghostrigger_autorig
