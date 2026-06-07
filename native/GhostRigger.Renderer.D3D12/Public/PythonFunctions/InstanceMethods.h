#pragma once

#include <cstddef>

namespace ghostrigger::phase15::ghostrigger_renderer_d3d12 {

using PythonFunctionDescriptorJson = const char* (*)();

struct PythonFunctionDescriptorEntry {
    const char* python_file;
    const char* qualname;
    const char* function_type;
    PythonFunctionDescriptorJson descriptor_json;
};

const char* src_adapters_rendering_direct3d_renderer_direct3drenderer_init_line_15_63a3b021_descriptor_json();
const char* src_adapters_rendering_direct3d_renderer_direct3drenderer_is_available_line_21_ad1b3dd8_descriptor_json();
const char* src_adapters_rendering_direct3d_renderer_direct3drenderer_reason_line_24_642745d0_descriptor_json();
const char* src_adapters_rendering_direct3d_renderer_direct3drenderer_get_capabilities_line_29_8ae24155_descriptor_json();
const char* src_adapters_rendering_direct3d_renderer_direct3drenderer_get_diagnostics_line_45_b8fcb653_descriptor_json();
const char* src_core_rendering_gpu_scene_helpers_compositemodel_init_line_200_c12006dd_descriptor_json();
const char* src_core_rendering_gpu_scene_helpers_compositemodel_getattr_line_261_4ff9158e_descriptor_json();
const char* src_core_rendering_gpu_scene_helpers_compositemodel_all_nodes_line_264_09c0cd80_descriptor_json();
const char* src_core_rendering_hardware_info_hardwarediagnostics_to_dict_line_41_dc705848_descriptor_json();
const char* src_core_rendering_hardware_info_hardwarediagnostics_lines_line_73_82d8df33_descriptor_json();

const PythonFunctionDescriptorEntry* instancemethods_descriptors(std::size_t& count);

} // namespace ghostrigger::phase15::ghostrigger_renderer_d3d12
