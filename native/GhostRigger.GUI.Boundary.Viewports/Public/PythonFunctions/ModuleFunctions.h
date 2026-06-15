#pragma once

#include <cstddef>

namespace ghostrigger::gui::boundary::viewports {

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

const NativeFunctionImplementation& getattr_line_68_20c2e042_native();
const NativeFunctionImplementation& dir_line_77_9e771612_native();
const NativeFunctionImplementation& transform_bar_stylesheet_line_8_ac72df50_native();
const NativeFunctionImplementation& getattr_line_53_8301ae8b_native();
const NativeFunctionImplementation& dir_line_69_1b14d4c1_native();
const NativeFunctionImplementation& icon_line_11_f42d4c27_native();
const NativeFunctionImplementation& gpu_brand_icon_line_19_41f1dd39_native();
const NativeFunctionImplementation& branded_control_icon_line_24_4e53b774_native();
const NativeFunctionImplementation& detect_gpu_brand_line_29_508ced69_native();
const NativeFunctionImplementation& gpu_icon_name_line_53_4723c85d_native();
const NativeFunctionImplementation& gpu_icon_line_62_ab15f180_native();
const NativeFunctionImplementation& navigation_profile_icon_line_71_218baef7_native();
const NativeFunctionImplementation& is_key_joint_name_line_60_44774def_native();
const NativeFunctionImplementation& classify_joint_color_line_64_e4d32256_native();
const NativeFunctionImplementation& weight_to_heatmap_color_line_18_cdcb55ad_native();
const NativeFunctionImplementation& getattr_line_19_42fcc11c_native();
const NativeFunctionImplementation& dir_line_29_bb5314bf_native();
const NativeFunctionImplementation& snake_case_line_33_6b027c77_native();
const NativeFunctionImplementation& pascal_case_line_47_9e6ff2a9_native();
const NativeFunctionImplementation& widget_template_line_51_1cf8e479_native();
const NativeFunctionImplementation& mixin_template_line_85_13a7f91a_native();
const NativeFunctionImplementation& create_custom_viewport_widget_line_105_4368fa97_native();
const NativeFunctionImplementation& getattr_line_21_9180ba79_native();
const NativeFunctionImplementation& dir_line_31_9bfc2cf2_native();

const NativeFunctionImplementation* modulefunctions_native_functions(std::size_t& count);

} // namespace ghostrigger::gui::boundary::viewports
