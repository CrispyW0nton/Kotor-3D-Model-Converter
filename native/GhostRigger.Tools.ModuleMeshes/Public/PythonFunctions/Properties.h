#pragma once

#include <cstddef>

namespace ghostrigger::phase15::ghostrigger_tools_modulemeshes {

using PythonFunctionDescriptorJson = const char* (*)();

struct PythonFunctionDescriptorEntry {
    const char* python_file;
    const char* qualname;
    const char* function_type;
    PythonFunctionDescriptorJson descriptor_json;
};

const char* src_core_modules_custom_module_packager_packagedmoduleresource_key_line_35_f11e45e7_descriptor_json();
const char* src_core_modules_module_categories_moduleinfo_label_line_25_06a18914_descriptor_json();
const char* src_core_modules_module_editor_controller_moduleeditorcontroller_project_line_33_3719cfbd_descriptor_json();
const char* src_core_modules_module_editor_model_moduleeditormodel_scene_line_29_c3d7753c_descriptor_json();
const char* src_core_modules_module_hydration_moduleresourcerecord_key_line_49_42d115cb_descriptor_json();
const char* src_core_modules_module_save_pipeline_modulereplacementresource_key_line_136_58506ade_descriptor_json();
const char* src_core_modules_module_save_pipeline_modulearchiveentry_key_line_154_3c786bf1_descriptor_json();
const char* src_core_walkmesh_walkmesh_renderer_walkmeshface_color_line_151_366a94f0_descriptor_json();
const char* src_core_walkmesh_walkmesh_renderer_walkmeshface_normal_line_155_2b51a16b_descriptor_json();
const char* src_core_walkmesh_walkmesh_renderer_walkmeshtogglecontroller_visible_line_753_0e217618_descriptor_json();
const char* src_core_walkmesh_walkmesh_renderer_walkmeshtogglecontroller_key_line_814_e16bcb57_descriptor_json();
const char* src_core_walkmesh_walkmesh_renderer_walkmeshtogglecontroller_overlay_count_line_819_771599f7_descriptor_json();

const PythonFunctionDescriptorEntry* properties_descriptors(std::size_t& count);

} // namespace ghostrigger::phase15::ghostrigger_tools_modulemeshes
