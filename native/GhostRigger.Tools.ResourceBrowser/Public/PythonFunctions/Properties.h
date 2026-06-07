#pragma once

#include <cstddef>

namespace ghostrigger::phase15::ghostrigger_tools_resourcebrowser {

using PythonFunctionDescriptorJson = const char* (*)();

struct PythonFunctionDescriptorEntry {
    const char* python_file;
    const char* qualname;
    const char* function_type;
    PythonFunctionDescriptorJson descriptor_json;
};

const char* src_core_resources_game_resource_provider_gameresourcerecord_resref_line_116_3d616c56_descriptor_json();
const char* src_core_resources_game_resource_provider_gameresourcerecord_restype_line_120_1d46f82f_descriptor_json();
const char* src_core_resources_game_resource_provider_gameresourcerecord_layer_line_124_3bab406c_descriptor_json();
const char* src_core_resources_game_resource_provider_gameresourcerecord_key_line_128_f409ca4e_descriptor_json();
const char* src_core_resources_game_resource_provider_gameresourceresult_address_line_147_0e30bfb9_descriptor_json();
const char* src_resources_game_library_resourceentry_is_model_line_148_43c8a66b_descriptor_json();
const char* src_resources_game_library_resourceentry_is_texture_line_158_fe34306f_descriptor_json();
const char* src_resources_game_library_resourceentry_ext_line_176_0604481f_descriptor_json();
const char* src_resources_game_library_resourceentry_filename_line_183_c3d15313_descriptor_json();
const char* src_resources_game_library_modellibraryentry_display_label_line_564_bd018b8d_descriptor_json();
const char* src_resources_game_library_modellibraryentry_display_label_rich_line_572_ec474d1b_descriptor_json();

const PythonFunctionDescriptorEntry* properties_descriptors(std::size_t& count);

} // namespace ghostrigger::phase15::ghostrigger_tools_resourcebrowser
