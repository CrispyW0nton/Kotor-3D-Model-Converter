#pragma once

#include <cstddef>

namespace ghostrigger::core::gui::viewports {

#ifndef GHOSTRIGGER_GUI_VIEWPORTS_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED
#define GHOSTRIGGER_GUI_VIEWPORTS_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED
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
#endif // GHOSTRIGGER_GUI_VIEWPORTS_NATIVE_FUNCTION_IMPLEMENTATION_DEFINED

const NativeFunctionImplementation& viewportconstructionmixin_active_renderer_line_388_169a686d_native();
const NativeFunctionImplementation& viewportconstructionmixin_active_renderer_backend_line_398_dd4723ef_native();
const NativeFunctionImplementation& viewportconstructionmixin_viewport_toolbar_chrome_visible_line_510_6ca847b5_native();
const NativeFunctionImplementation& viewportconstructionmixin_viewcube_chrome_visible_line_514_1fe6d360_native();
const NativeFunctionImplementation& viewportconstructionmixin_transform_typein_chrome_visible_line_518_c2ace669_native();
const NativeFunctionImplementation& viewporteventnavigationmixin_character_mode_line_396_8989c930_native();
const NativeFunctionImplementation& viewporteventnavigationmixin_ortho_mode_line_714_543586a3_native();
const NativeFunctionImplementation& viewportmeasurementcontrolsmixin_mesh_hover_enabled_line_34_0c8fc93e_native();
const NativeFunctionImplementation& viewportoverlaylayersmixin_weight_heatmap_enabled_line_268_87e036af_native();
const NativeFunctionImplementation& viewportoverlaylayersmixin_weight_heatmap_dot_size_line_272_49846575_native();
const NativeFunctionImplementation& viewportoverlaylayersmixin_joint_symmetry_enabled_line_436_a3c7510a_native();
const NativeFunctionImplementation& viewportoverlaylayersmixin_joint_dot_enabled_line_473_58b0e228_native();
const NativeFunctionImplementation& viewportoverlaylayersmixin_joint_dot_size_line_477_dfdb9a1f_native();
const NativeFunctionImplementation& viewportoverlaylayersmixin_joint_dot_opacity_line_481_d5c3937c_native();
const NativeFunctionImplementation& viewportscenemodelmixin_tex_cache_line_722_2d7365ee_native();
const NativeFunctionImplementation& floatingsnapviewwidget_ortho_button_line_138_7f8f61d2_native();
const NativeFunctionImplementation& viewportstatemixin_navigation_profile_line_353_d50c9674_native();
const NativeFunctionImplementation& viewporttransformcameramixin_thumbnail_widget_line_259_48c6e8ee_native();

const NativeFunctionImplementation* properties_native_functions(std::size_t& count);

} // namespace ghostrigger::core::gui::viewports
