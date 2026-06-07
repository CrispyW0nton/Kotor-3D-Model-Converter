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

const char* src_autorig_auto_rigger_rigtemplate_load_line_266_0f605af1_descriptor_json();
const char* src_autorig_cloth_rig_clothrigpreset_names_line_204_d261924b_descriptor_json();
const char* src_autorig_cloth_rig_clothrigpreset_get_line_208_148424dc_descriptor_json();
const char* src_autorig_retarget_engine_modelorientfixer_apply_line_181_43fa93c7_descriptor_json();
const char* src_autorig_retarget_engine_modelorientfixer_align_to_reference_line_307_f8ff80a8_descriptor_json();
const char* src_autorig_retarget_engine_scalesolver_solve_line_455_84919dd2_descriptor_json();

const PythonFunctionDescriptorEntry* classmethods_descriptors(std::size_t& count);

} // namespace ghostrigger::phase15::ghostrigger_autorig
