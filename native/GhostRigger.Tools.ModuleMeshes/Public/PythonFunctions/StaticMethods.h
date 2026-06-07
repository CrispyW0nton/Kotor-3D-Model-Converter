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

const char* src_core_level_kmap_validator_kmapvalidator_valid_transform_line_123_f2f62e68_descriptor_json();
const char* src_core_level_level_export_bridge_levelexportbridge_single_export_model_line_106_74e418b1_descriptor_json();
const char* src_core_modules_module_editor_controller_moduleeditorcontroller_blueprint_type_for_library_asset_line_165_6428786f_descriptor_json();
const char* src_core_walkmesh_walkmesh_renderer_walkmeshwriter_roundtrip_line_568_cd29482e_descriptor_json();
const char* src_core_walkmesh_walkmesh_renderer_walkmeshwriter_compute_adjacency_line_631_816fefe7_descriptor_json();
const char* src_core_walkmesh_walkmesh_renderer_walkmeshwriter_pack_line_665_044477c6_descriptor_json();
const char* src_gui_panels_module_editor_module_editor_properties_moduleeditorpropertiespanel_set_vector_line_85_4910d35b_descriptor_json();

const PythonFunctionDescriptorEntry* staticmethods_descriptors(std::size_t& count);

} // namespace ghostrigger::phase15::ghostrigger_tools_modulemeshes
