#pragma once

#include <cstddef>

namespace ghostrigger::phase15::ghostrigger_rendering {

using PythonFunctionDescriptorJson = const char* (*)();

struct PythonFunctionDescriptorEntry {
    const char* python_file;
    const char* qualname;
    const char* function_type;
    PythonFunctionDescriptorJson descriptor_json;
};

const char* src_core_rendering_gpu_scene_helpers_compositemodel_nodes_line_292_c770f0f1_descriptor_json();
const char* src_core_rendering_renderer_performance_renderbatch_draw_count_line_38_3388d90f_descriptor_json();
const char* src_core_rendering_renderer_performance_renderbatch_visible_count_line_42_fa4f1295_descriptor_json();
const char* src_core_rendering_renderer_performance_viewportframegovernor_frame_interval_s_line_131_2e9daa85_descriptor_json();
const char* src_core_rendering_renderer_performance_viewportframegovernor_dirty_line_135_2d2cbbcd_descriptor_json();
const char* src_core_rendering_renderer_performance_textureresidencyinfo_array_group_key_line_227_c8c5cceb_descriptor_json();
const char* src_core_rendering_renderer_performance_textureresidencyinfo_array_eligible_line_231_0401a809_descriptor_json();
const char* src_core_rendering_renderer_profiler_rendererframemetrics_fps_estimate_line_50_5623780c_descriptor_json();

const PythonFunctionDescriptorEntry* properties_descriptors(std::size_t& count);

} // namespace ghostrigger::phase15::ghostrigger_rendering
