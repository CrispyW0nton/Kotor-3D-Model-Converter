#pragma once

#include <cstddef>

namespace ghostrigger::phase15::ghostrigger_templates {

using PythonFunctionDescriptorJson = const char* (*)();

struct PythonFunctionDescriptorEntry {
    const char* python_file;
    const char* qualname;
    const char* function_type;
    PythonFunctionDescriptorJson descriptor_json;
};

const char* src_core_templates_template_builder_get_bones_for_version_line_325_8ee48708_descriptor_json();
const char* src_core_templates_template_builder_get_anim_slots_for_version_line_332_c7281819_descriptor_json();
const char* src_core_templates_template_builder_build_humanoid_template_line_339_bbc0530a_descriptor_json();
const char* src_core_templates_template_builder_add_placeholder_body_line_430_15dfa9e7_descriptor_json();
const char* src_core_templates_template_builder_save_template_manifest_line_473_0baef5db_descriptor_json();
const char* src_core_templates_template_builder_validate_animations_via_pykotor_line_521_9e959283_descriptor_json();
const char* src_core_templates_template_builder_check_model_eyeball_nodes_line_660_29303138_descriptor_json();
const char* src_core_templates_twoda_split_2da_line_line_345_e1fcb025_descriptor_json();

const PythonFunctionDescriptorEntry* modulefunctions_descriptors(std::size_t& count);

} // namespace ghostrigger::phase15::ghostrigger_templates
