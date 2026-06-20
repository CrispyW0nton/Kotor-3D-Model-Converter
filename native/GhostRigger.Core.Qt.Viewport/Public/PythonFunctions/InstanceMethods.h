#pragma once

#include <cstddef>

namespace ghostrigger::core::qt::viewport {

#ifndef GHOSTRIGGER_CORE_QT_VIEWPORT_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED
#define GHOSTRIGGER_CORE_QT_VIEWPORT_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED
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
#endif // GHOSTRIGGER_CORE_QT_VIEWPORT_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED

const NativeFunctionImplementation& cameragizmorenderer_construct_line_11_a6578952_native();
const NativeFunctionImplementation& cameragizmorenderer_set_theme_colors_line_36_55ae0baf_native();
const NativeFunctionImplementation& cameragizmorenderer_reset_theme_colors_line_51_de2741c1_native();
const NativeFunctionImplementation& cameragizmorenderer_set_native_palette_colors_line_62_7ccd7ee0_native();
const NativeFunctionImplementation& cameragizmorenderer_draw_line_82_e26fcd58_native();
const NativeFunctionImplementation& cameragizmorenderer_draw_camera_line_90_75e34c3c_native();
const NativeFunctionImplementation& cameragizmorenderer_draw_target_line_108_7d4550f0_native();
const NativeFunctionImplementation& cameragizmorenderer_draw_frustum_line_122_346970ea_native();
const NativeFunctionImplementation& cameragizmorenderer_camera_position_line_155_d3d21be1_native();
const NativeFunctionImplementation& cameragizmorenderer_camera_rotation_line_165_9cd361be_native();
const NativeFunctionImplementation& cameraoverlays_draw_line_7_0710b789_native();
const NativeFunctionImplementation& cameraoverlays_active_frame_rect_line_16_6a2efa6c_native();
const NativeFunctionImplementation& cameraoverlays_draw_letterbox_line_32_f67fab12_native();
const NativeFunctionImplementation& cameraoverlays_draw_safe_frame_line_52_ca817b68_native();
const NativeFunctionImplementation& cameraoverlays_draw_guides_line_62_4fe6b929_native();
const NativeFunctionImplementation& lightingviewportcontroller_construct_line_10_008aef57_native();
const NativeFunctionImplementation& lightingviewportcontroller_apply_to_renderer_line_17_99889bc9_native();
const NativeFunctionImplementation& framerenderer_construct_line_14_4f72f7ff_native();
const NativeFunctionImplementation& framerenderer_render_current_frame_line_20_b27a926e_native();
const NativeFunctionImplementation& framerenderer_render_to_file_line_68_94da0a3b_native();
const NativeFunctionImplementation& framerenderer_resolution_line_91_313ea057_native();
const NativeFunctionImplementation& framerenderer_snapshot_helpers_line_100_1f072412_native();
const NativeFunctionImplementation& framerenderer_set_helpers_line_116_c7b75807_native();
const NativeFunctionImplementation& framerenderer_restore_helpers_line_128_618b0eac_native();

const NativeFunctionImplementation* instancemethods_native_functions(std::size_t& count);

} // namespace ghostrigger::core::qt::viewport
