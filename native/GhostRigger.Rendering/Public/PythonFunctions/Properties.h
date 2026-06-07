#pragma once

#include <cstddef>

namespace ghostrigger::rendering {

#ifndef GHOSTRIGGER_RENDERING_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED
#define GHOSTRIGGER_RENDERING_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED
struct NativeFunctionImplementation {
    const char* project;
    const char* native_namespace;
    const char* python_file;
    const char* qualname;
    const char* callable_type;
    const char* implementation_status;
    bool native_first;
    bool python_runtime_required;
    bool python_fallback_allowed;
    const char* contract_json;
};
#endif // GHOSTRIGGER_RENDERING_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED

const NativeFunctionImplementation& compositemodel_nodes_line_292_c770f0f1_native();
const NativeFunctionImplementation& renderbatch_draw_count_line_38_3388d90f_native();
const NativeFunctionImplementation& renderbatch_visible_count_line_42_fa4f1295_native();
const NativeFunctionImplementation& viewportframegovernor_frame_interval_s_line_131_2e9daa85_native();
const NativeFunctionImplementation& viewportframegovernor_dirty_line_135_2d2cbbcd_native();
const NativeFunctionImplementation& textureresidencyinfo_array_group_key_line_227_c8c5cceb_native();
const NativeFunctionImplementation& textureresidencyinfo_array_eligible_line_231_0401a809_native();
const NativeFunctionImplementation& rendererframemetrics_fps_estimate_line_50_5623780c_native();

const NativeFunctionImplementation* properties_native_functions(std::size_t& count);

} // namespace ghostrigger::rendering
