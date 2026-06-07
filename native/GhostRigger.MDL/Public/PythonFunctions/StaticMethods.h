#pragma once

#include <cstddef>

namespace ghostrigger::phase15::ghostrigger_mdl {

using PythonFunctionDescriptorJson = const char* (*)();

struct PythonFunctionDescriptorEntry {
    const char* python_file;
    const char* qualname;
    const char* function_type;
    PythonFunctionDescriptorJson descriptor_json;
};

const char* src_core_mdl_mdl_parser_mdlbinaryparser_apply_bind_pose_controllers_line_315_3f0185ac_descriptor_json();
const char* src_core_mdl_mdl_parser_mdlbinaryparser_generate_missing_normals_line_329_7f0e1ae8_descriptor_json();
const char* src_core_mdl_mdl_porter_mdlbinarywriter_validate_animation_export_tree_line_1294_b52fe53c_descriptor_json();
const char* src_core_mdl_mdl_writer_mdlbinarywriter_read_animation_offsets_line_401_2e75a594_descriptor_json();
const char* src_core_mdl_mdl_writer_mdlbinarywriter_read_animation_name_line_418_a543d9e8_descriptor_json();
const char* src_core_mdl_mdl_writer_mdlbinarywriter_read_name_table_line_426_679d4a28_descriptor_json();
const char* src_core_mdl_mdl_writer_mdlbinarywriter_animation_export_key_times_line_1692_dd1e2011_descriptor_json();
const char* src_core_mdl_mdl_writer_mdlbinarywriter_normalized_xyzw_line_1712_249fd32e_descriptor_json();
const char* src_core_mdl_mdl_writer_mdlbinarywriter_validate_animation_export_tree_line_1739_9c16ae75_descriptor_json();

const PythonFunctionDescriptorEntry* staticmethods_descriptors(std::size_t& count);

} // namespace ghostrigger::phase15::ghostrigger_mdl
