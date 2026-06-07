#pragma once

#include <cstddef>

namespace ghostrigger::phase15::ghostrigger_graphics {

using PythonFunctionDescriptorJson = const char* (*)();

struct PythonFunctionDescriptorEntry {
    const char* python_file;
    const char* qualname;
    const char* function_type;
    PythonFunctionDescriptorJson descriptor_json;
};

const char* src_core_graphics_tpc_decompress_dxt1_bytes_e_line_133_74538bab_descriptor_json();
const char* src_core_graphics_tpc_decompress_dxt5_bytes_e_line_174_a7bf9284_descriptor_json();
const char* src_core_graphics_tpc_load_tpc_bytes_legacy_inner_flip_line_496_adeeec2f_descriptor_json();
const char* src_core_graphics_tpc_extract_txi_from_tpc_legacy_mip_sz_fn_line_663_34fe55e0_descriptor_json();
const char* src_core_graphics_tpc_extract_txi_from_tpc_legacy_mip_sz_fn_line_691_bc8f9005_descriptor_json();
const char* src_core_graphics_tpc_extract_txi_from_tpc_legacy_mip_sz_fn_line_697_9c5bbaff_descriptor_json();
const char* src_core_graphics_tpc_render_utils_decompress_dxt1_bytes_e_line_164_7b595deb_descriptor_json();
const char* src_core_graphics_tpc_render_utils_decompress_dxt5_bytes_e_line_202_27725da1_descriptor_json();
const char* src_core_graphics_tpc_render_utils_load_tpc_bytes_flip_line_318_544aafa3_descriptor_json();

const PythonFunctionDescriptorEntry* nestedfunctions_descriptors(std::size_t& count);

} // namespace ghostrigger::phase15::ghostrigger_graphics
